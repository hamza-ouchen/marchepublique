"""Ingest downloaded public packages and fill documented tender fields."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import closing
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from urllib.parse import quote
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from a2a_env import charger_env

charger_env()

import collect_documents
import cps_extract
import cps_ingest
import db_cps
from scrape_portal import portal_identity
from storage import download_bytes, make_uploader, upload_bytes

ARCHIVE_BUCKET = "tender-originaux"


def _amounts(text, label):
    number = r"(?:\d{1,3}(?:[ .\u00a0\u202f]\d{3})+|\d+)(?:[,.]\d{1,2})?"
    pattern = rf"(?<![\w])(?:{label})[^\d;]{{0,100}}?({number})\s*(?:MAD|DHS?|dirhams)\b"
    amounts = set()
    for raw in re.findall(pattern, text, re.I):
        decimal_suffix = re.search(r"[,.](\d{1,2})$", raw)
        integer = raw[:decimal_suffix.start()] if decimal_suffix else raw
        amount = Decimal(re.sub(r"\D", "", integer))
        if decimal_suffix:
            amount += Decimal("0." + decimal_suffix[1])
        if amount > 0:
            amounts.add(amount)
    return amounts


def _only(values):
    return next(iter(values)) if len(values) == 1 else None


def _document_fields(reference, rows):
    amounts, cautions, durations, dates_publication, dates_remise = (
        set(), set(), set(), set(), set()
    )
    lots, qualifications, evidence = set(), set(), []
    amount_docs, caution_docs = {}, {}
    publication_times, deadline_times = set(), set()
    for row in rows:
        text = re.sub(r"\s+", " ", row["extracted_text"])
        amount = _amounts(text, r"montant estimatif|montant pr[ée]visionnel|estimation (?:TTC|du co[uû]t|des prestations|des travaux|du ma[iî]tre d.ouvrage)")
        caution = _amounts(text, r"cautionnement provisoire|caution provisoire")
        duration = {int(value) for value in re.findall(
            r"(?:d[ée]lai|dur[ée]e) d.ex[ée]cution[^\d;]{0,70}(\d{1,4})\s+jours?\b", text, re.I
        ) if int(value) > 0}
        detail = cps_extract.extract_detail(text, row["filename"] or "")
        amounts.update(amount)
        cautions.update(caution)
        for value in amount:
            amount_docs.setdefault(value, []).append(row["id"])
        for value in caution:
            caution_docs.setdefault(value, []).append(row["id"])
        durations.update(duration)
        if detail["date_publication"]:
            dates_publication.add(date.fromisoformat(detail["date_publication"]))
            if detail.get("heure_publication"):
                publication_times.add((detail["date_publication"], detail["heure_publication"]))
        if detail["date_remise"]:
            dates_remise.add(date.fromisoformat(detail["date_remise"]))
            if detail.get("heure_remise"):
                deadline_times.add((detail["date_remise"], detail["heure_remise"]))
        lots.update(detail["lots"])
        qualifications.update(value for value in detail["qualifications_exigees"] if re.search(
            r"certificat de qualification|qualification et classification|classe minimale|agr[ée]ment.{0,30}domaine",
            value, re.I
        ))
        if amount or caution or duration or detail["signals"]:
            evidence.append(row["id"])
    if not evidence:
        return None
    amount, caution = _only(amounts), _only(cautions)
    publication, deadline = _only(dates_publication), _only(dates_remise)
    publication_time = _only(publication_times)
    deadline_time = _only(deadline_times)
    return dict(reference=reference, amount=amount, caution=caution, duration=_only(durations),
                publication=publication, deadline=deadline, lots=sorted(lots),
                publication_time=publication_time[1] if publication_time and publication else None,
                deadline_time=deadline_time[1] if deadline_time and deadline else None,
                qualifications=sorted(qualifications), evidence=json.dumps(evidence),
                amount_docs=json.dumps(amount_docs.get(amount, [])),
                caution_docs=json.dumps(caution_docs.get(caution, [])))


_APPLY_FIELDS = """
        UPDATE tenders SET
          montant_mad = CASE WHEN montant_mad IS NULL
            AND (%(amount)s::numeric >= coalesce(caution_mad, %(caution)s::numeric, 0))
            THEN %(amount)s::numeric ELSE montant_mad END,
          caution_mad = CASE WHEN caution_mad IS NULL AND (%(caution)s::numeric <=
            coalesce(montant_mad, %(amount)s::numeric, %(caution)s::numeric))
            THEN %(caution)s::numeric ELSE caution_mad END,
          delai_jours = coalesce(delai_jours, %(duration)s::int),
          date_publication = CASE WHEN date_publication IS NULL AND
            %(publication)s::date <= coalesce(date_remise, %(deadline)s::date, %(publication)s::date)
            THEN %(publication)s::date ELSE date_publication END,
          date_remise = CASE WHEN date_remise IS NULL AND
            %(deadline)s::date >= coalesce(date_publication, %(publication)s::date, %(deadline)s::date)
            THEN %(deadline)s::date ELSE date_remise END,
          heure_publication = CASE WHEN heure_publication IS NULL AND
            (date_publication=%(publication)s::date OR (date_publication IS NULL AND
             %(publication)s::date <= coalesce(date_remise, %(deadline)s::date, %(publication)s::date)))
            THEN %(publication_time)s::time ELSE heure_publication END,
          heure_remise = CASE WHEN heure_remise IS NULL AND
            (date_remise=%(deadline)s::date OR (date_remise IS NULL AND
             %(deadline)s::date >= coalesce(date_publication, %(publication)s::date, %(deadline)s::date)))
            THEN %(deadline_time)s::time ELSE heure_remise END,
          lots = CASE WHEN cardinality(lots)=0 THEN %(lots)s::text[] ELSE lots END,
          qualifications_exigees = CASE WHEN cardinality(qualifications_exigees)=0
            THEN %(qualifications)s::text[] ELSE qualifications_exigees END,
          extraction = extraction || jsonb_build_object('documents_preuves', %(evidence)s::jsonb)
            || CASE WHEN %(amount)s::numeric IS NOT NULL AND
                (montant_mad=%(amount)s::numeric OR
                 (montant_mad IS NULL AND %(amount)s::numeric >= coalesce(caution_mad,%(caution)s::numeric,0)))
              THEN jsonb_build_object('preuves_montant_mad', %(amount_docs)s::jsonb) ELSE '{}'::jsonb END
            || CASE WHEN %(caution)s::numeric IS NOT NULL AND
                (caution_mad=%(caution)s::numeric OR
                 (caution_mad IS NULL AND %(caution)s::numeric <= coalesce(montant_mad,%(amount)s::numeric,%(caution)s::numeric)))
              THEN jsonb_build_object('preuves_caution_mad', %(caution_docs)s::jsonb) ELSE '{}'::jsonb END
        WHERE reference=%(reference)s
        """


def refresh_tender(reference):
    rows = db_cps.query(
        "SELECT id, filename, extracted_text FROM tender_documents "
        "WHERE reference=%s AND statut IN ('extracted','ready') AND extracted_text IS NOT NULL",
        (reference,),
    )
    fields = _document_fields(reference, rows)
    return db_cps.execute(_APPLY_FIELDS, fields) if fields else 0


def refresh_open_tenders(workers, date_cible=None):
    rows = db_cps.query(
        """
        SELECT DISTINCT t.reference
        FROM tenders t JOIN tender_documents d USING(reference)
        WHERE t.statut='ouvert' AND d.statut IN ('extracted','ready')
          AND (%s::date IS NULL OR t.date_collecte=%s::date)
          AND (t.montant_mad IS NULL OR t.caution_mad IS NULL OR t.delai_jours IS NULL
               OR t.date_remise IS NULL OR t.date_publication IS NULL
               OR t.heure_remise IS NULL OR t.heure_publication IS NULL
               OR cardinality(t.lots)=0 OR cardinality(t.qualifications_exigees)=0)
        """, (date_cible, date_cible),
    )
    references = [row["reference"] for row in rows]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for offset in range(0, len(references), 40):
            batch = references[offset:offset + 40]
            documents = {reference: [] for reference in batch}
            for row in db_cps.query(
                "SELECT reference,id,filename,extracted_text FROM tender_documents "
                "WHERE reference=ANY(%s) AND statut IN ('extracted','ready') AND extracted_text IS NOT NULL",
                (batch,),
            ):
                documents[row["reference"]].append(row)
            updates = [fields for fields in pool.map(
                lambda ref: _document_fields(ref, documents[ref]), batch
            ) if fields]
            if updates:
                with closing(db_cps.connect()) as conn:
                    with conn.transaction(), conn.cursor() as cursor:
                        cursor.executemany(_APPLY_FIELDS, updates)
    return len(references)


def run_ao_fallback(date_cible, seconds, portal_unavailable=False):
    if seconds <= 0:
        return {"requested": 0, "downloaded": 0, "status": "disabled"}
    rows = db_cps.query(
        """
        SELECT reference,source_url FROM tenders t
        WHERE statut='ouvert' AND (
          enrich_error='dce_form' OR enrich_error LIKE 'detail:%%'
          OR (%s AND t.offer_type IN ('appel_offres','consultation')
            AND NOT EXISTS (SELECT 1 FROM tender_documents d
                            WHERE d.reference=t.reference AND d.statut IN ('stored','extracted','ready')))
        )
          AND (date_remise IS NULL OR date_remise >= %s::date)
          AND NOT EXISTS (SELECT 1 FROM tender_documents d WHERE d.reference=t.reference
                          AND d.source_url LIKE 'https://www.aomaroc.com/cps?%%')
        ORDER BY (date_collecte=%s::date) DESC,enrich_attempts,date_remise NULLS LAST,reference
        """, (portal_unavailable, date_cible, date_cible),
    )
    offers = [{"id": identity, "url": row["source_url"], "type": "consultation"}
              for row in rows if (identity := portal_identity(row["source_url"]))
              and identity.startswith("consultation:")]
    if not offers:
        return {"requested": 0, "downloaded": 0, "status": "nothing_pending"}
    uploader = make_uploader()
    script = Path(__file__).with_name("download_public_documents.cjs")
    status = "completed"
    with tempfile.TemporaryDirectory(prefix="sou9na-ao-") as folder:
        root = Path(folder)
        queue = root / "offers.json"
        queue.write_text(json.dumps({"offers": offers}), encoding="utf-8")
        try:
            process = subprocess.run(
                [os.getenv("DOCUMENT_NODE", "node"), str(script), "ao-maroc", str(queue), str(root)],
                timeout=seconds + 15, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace",
                env={**os.environ, "DOCUMENT_BROWSER_SECONDS": str(seconds)},
            )
            if process.returncode:
                status = "browser_error"
            elif '"timedOut":true' in process.stdout:
                status = "time_budget"
        except subprocess.TimeoutExpired:
            status = "time_budget"
        except FileNotFoundError:
            status = "browser_unavailable"
        manifest = root / "download-results.json"
        results = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else []
        refs = {portal_identity(row["source_url"]): row["reference"] for row in rows}
        downloaded = ingested = 0
        for item in results:
            name = item.get("document")
            if not name or item["id"] not in refs or Path(name).name != name:
                continue
            downloaded += 1
            result = _ingest((refs[item["id"]], item["document_source"], root / name), uploader, True)
            extracted = sum(x["status"] == "extracted" or x.get("reason") == "already_ingested"
                            for x in result["documents"] if x.get("filename", "").lower().endswith(".pdf"))
            if extracted:
                collect_documents._mark(refs[item["id"]], {"saved": extracted})
                ingested += extracted
    return {"requested": len(offers), "downloaded": downloaded, "pdf_ingested": ingested, "status": status}


def _upload_original(reference, source_url, path, data, digest, existing_objects=()):
    is_pdf = data.startswith(b"%PDF-") and len(data) <= cps_ingest.MAX_PDF_BYTES
    if is_pdf:
        bucket, storage_path, mime = "cps-originaux", f"versions/{digest}.pdf", "application/pdf"
    else:
        ext, mime = ("zip", "application/zip") if data.startswith(b"PK") else ("bin", "application/octet-stream")
        bucket, storage_path = ARCHIVE_BUCKET, f"originals/{digest}.{ext}"
    if (bucket, storage_path) not in existing_objects:
        storage_path = upload_bytes(bucket, storage_path, data, mime)
    return dict(reference=reference, storage_bucket=bucket, storage_path=storage_path,
                sha256=digest, filename=path.name, mime=mime, size_bytes=len(data),
                source_url=source_url, downloaded_at=datetime.now(timezone.utc).isoformat())


def _save_originals(rows):
    db_cps.execute(
        """
        INSERT INTO tender_documents
          (reference, storage_bucket, storage_path, sha256, doc_type, filename, mime,
           size_bytes, source_url, statut, downloaded_at, sections)
        SELECT reference,storage_bucket,storage_path,sha256,'DCE',filename,mime,
               size_bytes,source_url,'stored',downloaded_at,0
        FROM jsonb_to_recordset(%s::jsonb) AS d(
          reference text, storage_bucket text, storage_path text, sha256 text,
          filename text, mime text, size_bytes bigint, source_url text, downloaded_at timestamptz
        )
        ON CONFLICT (reference, sha256) DO NOTHING
        """,
        (json.dumps(rows),),
    )


def _store_original(reference, source_url, path, data):
    digest = hashlib.sha256(data).hexdigest()
    existing = db_cps.tender_document_by_hash(reference, digest)
    if existing:
        return {"filename": path.name, "status": "skipped", "reason": "already_ingested"}
    _save_originals([_upload_original(reference, source_url, path, data, digest)])
    document = db_cps.tender_document_by_hash(reference, digest)
    return {"filename": path.name, "status": "stored", "document_id": document["id"]}


def _extract_package(reference, source_url, name, data, uploader):
    results = []
    for filename, pdf in collect_documents.pdf_files("file:///" + quote(name), data):
        kind = "CPS" if re.search(r"\bcps\b|prescriptions sp", filename, re.I) else (
            "ADDITIF" if re.search(r"additif|addenda|rectificatif|avenant", filename, re.I) else "DCE"
        )
        try:
            result = cps_ingest.ingest_cps(reference, pdf, filename=filename, doc_type=kind,
                                           source_url=source_url, storage_uploader=uploader)
        except Exception as exc:
            result = {"status": "echec", "reason": type(exc).__name__}
        results.append({"filename": filename, **{key: value for key, value in result.items()
                                                if key != "signals"}})
    refresh_tender(reference)
    return results


def _ingest(job, uploader, store_originals):
    reference, source_url, path = job
    results = []
    try:
        data = path.read_bytes()
        if store_originals and not data.startswith(b"%PDF-"):
            try:
                results.append(_store_original(reference, source_url, path, data))
            except Exception as exc:
                results.append({"filename": path.name, "status": "echec", "reason": type(exc).__name__})
        results.extend(_extract_package(reference, source_url, path.name, data, uploader))
    except Exception as exc:
        results.append({"status": "echec", "reason": type(exc).__name__})
    return {"reference": reference, "package": path.name, "documents": results}


def _process_stored(row, uploader):
    try:
        data = download_bytes(row["storage_bucket"], row["storage_path"])
        if hashlib.sha256(data).hexdigest() != row["sha256"]:
            raise ValueError("Stored object, unexpected SHA-256")
        name = row["filename"] or Path(row["storage_path"]).name
        results = _extract_package(row["reference"], row["source_url"], name, data, uploader)
        if row["mime"] == "application/zip":
            with ZipFile(io.BytesIO(data)) as archive:
                total_pdfs = sum(collect_documents.is_pdf_entry(item) for item in archive.infolist())
            complete = len(results) == total_pdfs and all(
                x["status"] == "extracted" or x.get("reason") == "already_ingested" for x in results
            )
            if complete:
                db_cps.execute(
                    "UPDATE tender_documents SET extraction=%s WHERE id=%s AND statut='stored'",
                    ("archive_pdf_processed" if total_pdfs else "archive_no_pdf", row["id"]),
                )
        return {"reference": row["reference"], "package": row["filename"], "documents": results}
    except Exception as exc:
        return {"reference": row["reference"], "package": row["filename"],
                "documents": [{"status": "echec", "reason": type(exc).__name__}]}


def process_stored_tenders(workers, date_cible=None, seconds=None):
    if seconds is not None and seconds <= 0:
        return {"attempted": 0, "pending": None}
    uploader = make_uploader()
    if uploader is None:
        raise RuntimeError("Supabase Storage credentials are required")
    rows = db_cps.query(
        "SELECT d.id,d.reference,d.storage_bucket,d.storage_path,d.sha256,d.filename,d.mime,d.source_url "
        "FROM tender_documents d JOIN tenders t USING (reference) "
        "WHERE d.statut IN ('stored','echec') AND t.statut='ouvert' AND t.offer_type IS NOT NULL "
        "AND d.mime IN ('application/pdf','application/zip') "
        "AND coalesce(d.extraction,'') NOT IN ('archive_pdf_processed','archive_no_pdf') "
        "AND d.storage_path ~ '^(versions|originals)/' "
        "ORDER BY (t.date_collecte=%s::date) DESC NULLS LAST,d.id", (date_cible,),
    )
    started = time.monotonic()
    attempted = extracted = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for i in range(0, len(rows), workers):
            if seconds is not None and time.monotonic() - started >= seconds:
                break
            for result in pool.map(lambda row: _process_stored(row, uploader), rows[i:i + workers]):
                attempted += 1
                extracted += sum(x["status"] == "extracted" for x in result["documents"])
    return {"attempted": attempted, "pending": len(rows) - attempted, "pdf_extracted": extracted}


def _store_many(jobs, workers):
    references = list({reference for reference, _, _ in jobs})
    known = {(x["reference"], x["sha256"]) for x in db_cps.query(
        "SELECT reference, sha256 FROM tender_documents WHERE reference=ANY(%s)", (references,)
    )}
    existing_objects = {(x["bucket_id"], x["name"]) for x in db_cps.query(
        "SELECT bucket_id, name FROM storage.objects WHERE bucket_id IN (%s, %s)",
        ("cps-originaux", ARCHIVE_BUCKET),
    )}

    def upload(job):
        reference, source_url, path = job
        try:
            data = path.read_bytes()
            digest = hashlib.sha256(data).hexdigest()
            if (reference, digest) in known:
                return None, {"reference": reference, "package": path.name, "status": "already_ingested"}
            return _upload_original(reference, source_url, path, data, digest, existing_objects), None
        except Exception as exc:
            return None, {"reference": reference, "package": path.name,
                          "status": "echec", "reason": str(exc)[:100]}

    def flush(batch):
        if batch:
            _save_originals(batch)
            for row in batch:
                print(json.dumps({"reference": row["reference"], "package": row["filename"],
                                  "status": "stored"}, ensure_ascii=False), flush=True)

    batch = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for future in as_completed([pool.submit(upload, job) for job in jobs]):
            row, status = future.result()
            if status:
                print(json.dumps(status, ensure_ascii=False), flush=True)
            else:
                batch.append(row)
                if len(batch) == 25:
                    flush(batch)
                    batch.clear()
    flush(batch)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--refresh-existing", action="store_true")
    parser.add_argument("--store-originals", action="store_true")
    parser.add_argument("--store-only", action="store_true")
    parser.add_argument("--process-stored", action="store_true")
    args = parser.parse_args()
    if args.refresh_existing:
        print(json.dumps({"reviewed_tenders": refresh_open_tenders(args.workers)}), flush=True)
    if args.manifest is None and not args.process_stored:
        return
    uploader = make_uploader()
    if (args.store_only or args.store_originals) and uploader is None:
        parser.error("L’archivage des originaux est désactivé ou indisponible.")
    if args.process_stored:
        print(json.dumps(process_stored_tenders(args.workers)), flush=True)
    if args.manifest is None:
        return
    rows = db_cps.query("SELECT reference, source_url FROM tenders WHERE statut='ouvert'")
    references = {portal_identity(x["source_url"]): x["reference"] for x in rows}
    folder = args.manifest.resolve().parent
    jobs = []
    for item in json.loads(args.manifest.read_text(encoding="utf-8")):
        if not item.get("document"):
            continue
        source_url = item["source_url"]
        reference = references.get(portal_identity(source_url))
        if reference is None:
            print(json.dumps({"status": "unmatched_tender", "source_url": source_url}), flush=True)
            continue
        package = (folder / item["document"]).resolve()
        if not package.is_relative_to(folder):
            raise ValueError("Package path outside manifest directory")
        jobs.append((reference, item.get("document_source") or source_url, package))
    if args.store_only:
        _store_many(jobs, args.workers)
        return
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(_ingest, job, uploader, args.store_originals) for job in jobs]
        for future in as_completed(futures):
            print(json.dumps(future.result(), ensure_ascii=False, default=str), flush=True)


if __name__ == "__main__":
    main()
