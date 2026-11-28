"""Second worker: scrape official portail DCE packs for tenders that have
neither database documents nor a local ZIP folder. DB-only, no storage upload.

Uses fetch_dce_zip_fast() (official portal form POST, bounded timeout), cps_ingest.ingest_cps
with storage_uploader=None, and enrich_tender_documents._APPLY_FIELDS to fill
missing tender fields. Runs independently of the local-ZIP extraction lanes.

Usage:
    py -B portal_documents_worker.py --workers 8
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "04-langgraph"))
sys.path.insert(0, str(ROOT / "04-langgraph" / "inspecteur"))

from a2a_env import charger_env  # noqa: E402

charger_env()

import cps_ingest  # noqa: E402
import db_cps  # noqa: E402
import requests  # noqa: E402
from enrich_tender_documents import _APPLY_FIELDS  # noqa: E402
from inspecteur import config  # noqa: E402
from inspecteur import cps_dce  # noqa: E402
from scrape_portal import portal_identity  # noqa: E402

WORK = ROOT / "portal-documents"
WORK.mkdir(exist_ok=True)
STATE_FILE = WORK / "progress.json"
LOCK_FILE = WORK / "active.lock"
ZIPS = ROOT / "documents_offres_aomaroc" / "zips"

FIELDS = ("montant_mad", "caution_mad", "delai_jours", "date_publication",
          "date_remise", "heure_publication", "heure_remise", "lots",
          "qualifications_exigees")
FIELD_LIST = ",".join(FIELDS)
MAX_ATTEMPTS = 4
BATCH_SIZE = 24
POST_TIMEOUT_S = 45.0
REQUEST_DELAY_S = max(config.PORTAL_DELAY_S, 2.0)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def local_identities() -> set[str]:
    found: set[str] = set()
    for base in (ZIPS, ZIPS / "agent-2"):
        for path in base.glob("*.zip"):
            match = re.fullmatch(r"(\d+)_([a-z0-9]+)", path.stem, re.I)
            if match:
                found.add(f"consultation:{match[2].lower()}:{match[1]}")
    return found


def build_candidates() -> list[dict]:
    local = local_identities()
    rows = db_cps.query(
        "SELECT reference, source_url, statut, date_remise FROM tenders t "
        "WHERE NOT EXISTS (SELECT 1 FROM tender_documents d WHERE d.reference=t.reference) "
        "  AND source_url IS NOT NULL AND source_url <> ''"
    )
    candidates: list[dict] = []
    for row in rows:
        ident = portal_identity(row.get("source_url"))
        if not ident or not ident.startswith("consultation:") or ident in local:
            continue
        keys = cps_dce.parse_portal_keys(row["source_url"])
        if not keys:
            continue
        candidates.append({
            "reference": row["reference"],
            "source_url": row["source_url"],
            "identity": ident,
            "refc": keys[0],
            "org": keys[1],
            "statut": row["statut"],
            "date_remise": (row["date_remise"].isoformat() if row.get("date_remise") else None),
        })
    candidates.sort(key=lambda c: (c["statut"] != "ouvert", c["date_remise"] is None,
                                   c["date_remise"] or "", c["reference"]))
    return candidates


def load_state() -> dict:
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    else:
        state = {
            "version": 1,
            "started_at": now_iso(),
            "updated_at": None,
            "items": {},
            "stats": {"candidates": 0, "processed": 0, "succeeded": 0, "failed": 0,
                      "documents_inserted": 0, "sections_inserted": 0,
                      "field_updates": 0, "characters_added": 0},
        }
    state.setdefault("items", {})
    state.setdefault("stats", {})
    for key in ("candidates", "processed", "succeeded", "failed",
                "documents_inserted", "sections_inserted", "field_updates",
                "characters_added"):
        state["stats"].setdefault(key, 0)
    return state


def save_state(state: dict) -> None:
    state["updated_at"] = now_iso()
    payload = json.dumps(state, ensure_ascii=False, indent=1)
    temp = STATE_FILE.with_suffix(".json.tmp")
    temp.write_text(payload, encoding="utf-8")
    try:
        os.replace(temp, STATE_FILE)
    except PermissionError:
        # Windows can hold progress.json open briefly (editor / antivirus).
        # Saving in place keeps the worker alive; the payload is already complete.
        STATE_FILE.write_text(payload, encoding="utf-8")
        temp.unlink(missing_ok=True)


def fetch_dce_zip_fast(session: requests.Session, dce_url: str) -> bytes:
    """Same official portal flow as cps_dce, with a bounded final post."""
    response = session.get(dce_url, timeout=config.REQUEST_TIMEOUT_S)
    if response.status_code != 200:
        raise cps_dce.DceError(f"page dce http {response.status_code}")
    fields = cps_dce._parse_form(response.text)
    if not fields:
        raise cps_dce.DceError("formulaire introuvable sur la page DCE")
    for key, value in config.DCE_FORM.items():
        fields[f"ctl0$CONTENU_PAGE$EntrepriseFormulaireDemande${key}"] = value
    fields["ctl0$CONTENU_PAGE$EntrepriseFormulaireDemande$accepterConditions"] = "on"
    fields[cps_dce._VALIDATE_BTN] = "Valider"
    fields["PRADO_POSTBACK_TARGET"] = cps_dce._VALIDATE_BTN
    second = session.post(dce_url, data=fields, timeout=config.REQUEST_TIMEOUT_S)
    if second.status_code != 200 or cps_dce._COMPLETE_BTN.split("$")[-1] not in second.text:
        raise cps_dce.DceError("formulaire DCE refusé (completeDownload absent)")
    fields2 = cps_dce._parse_form(second.text)
    fields2["PRADO_POSTBACK_TARGET"] = cps_dce._COMPLETE_BTN
    final = session.post(dce_url, data=fields2, timeout=POST_TIMEOUT_S)
    if final.status_code != 200 or not final.content:
        raise cps_dce.DceError("téléchargement DCE vide")
    ctype = (final.headers.get("Content-Type") or "").lower()
    if "zip" in ctype or final.content[:4] == b"PK\x03\x04":
        return final.content
    raise cps_dce.DceError("réponse non ZIP après completeDownload")


def apply_fields(reference: str) -> int:
    """Return number of tender fields actually changed."""
    with db_cps.connect() as conn, conn.transaction():
        before = conn.execute(
            f"SELECT {FIELD_LIST} FROM tenders WHERE reference=%s FOR UPDATE",
            (reference,),
        ).fetchone()
        if not before:
            return 0
        values = _document_values(reference)
        if not values:
            return 0
        after = conn.execute(_APPLY_FIELDS + " RETURNING " + FIELD_LIST, values).fetchone()
        return sum(1 for field in FIELDS if before[field] != after[field])


def _document_values(reference: str):
    from enrich_tender_documents import _document_fields

    rows = db_cps.query(
        "SELECT id, filename, extracted_text FROM tender_documents "
        "WHERE reference=%s AND statut IN ('extracted','ready') AND extracted_text IS NOT NULL",
        (reference,),
    )
    return _document_fields(reference, rows)


def process_candidate(candidate: dict) -> dict:
    ref = candidate["reference"]
    out = {"documents_inserted": 0, "sections_inserted": 0,
           "field_updates": 0, "characters_added": 0, "error": None}
    session = requests.Session()
    session.headers.update({"User-Agent": config.USER_AGENT})
    try:
        detail_url = candidate["source_url"]
        response = session.get(detail_url, timeout=config.REQUEST_TIMEOUT_S)
        if response.status_code != 200:
            raise cps_dce.DceError(f"detail http {response.status_code}")

        zip_bytes = None
        match = cps_dce._DCE_LINK_RE.search(response.text)
        if match:
            dce_url = urljoin(response.url, match.group(1))
            zip_bytes = fetch_dce_zip_fast(session, dce_url)
            source_url = dce_url
        else:
            # Some notices expose only a direct AJL/avis PDF and no DCE form.
            from inspecteur import cps_download

            sources = cps_download.find_pdf_links(response.url, response.text)
            if not sources:
                raise cps_dce.DceError("aucun lien DCE ni PDF direct")
            for pdf_url in sources[:cps_dce.config.MAX_DOCS_PER_TENDER]:
                try:
                    pdf = cps_download.download_pdf(pdf_url, session=session)
                except Exception:
                    continue
                name = pdf_url.rsplit("/", 1)[-1][:120] or "avis.pdf"
                result = cps_ingest.ingest_cps(
                    ref, pdf, source_url=pdf_url,
                    doc_type=cps_dce.classify_doc_type(name), filename=name,
                    storage_uploader=None,
                )
                if result.get("status") == "extracted":
                    out["documents_inserted"] += 1
                    out["sections_inserted"] += int(result.get("sections") or 0)
                    out["characters_added"] += int(result.get("char_count") or 0)
            if not out["documents_inserted"]:
                raise cps_dce.DceError("PDF directs indisponibles")
            source_url = sources[0]

        if zip_bytes:
            for name, pdf in cps_dce.pdfs_from_zip(zip_bytes):
                if len(pdf) > cps_ingest.MAX_PDF_BYTES:
                    continue
                result = cps_ingest.ingest_cps(
                    ref, pdf, source_url=source_url,
                    doc_type=cps_dce.classify_doc_type(name), filename=name,
                    storage_uploader=None,
                )
                if result.get("status") == "extracted":
                    out["documents_inserted"] += 1
                    out["sections_inserted"] += int(result.get("sections") or 0)
                    out["characters_added"] += int(result.get("char_count") or 0)

        out["field_updates"] = apply_fields(ref)
        db_cps.execute(
            "UPDATE tenders SET enriched_at=now(), enrich_attempts=0, "
            "enrich_next_at=NULL, enrich_error=NULL WHERE reference=%s", (ref,)
        )
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"[:240]
    finally:
        session.close()
        time.sleep(REQUEST_DELAY_S)
    return out


def report(state: dict, candidates: list[dict]) -> None:
    stats = state["stats"]
    active = {candidate["reference"] for candidate in candidates}
    items = {ref: item for ref, item in state["items"].items() if ref in active}
    succeeded = sum(1 for item in items.values() if item.get("status") == "done")
    failed = sum(1 for item in items.values() if item.get("status") == "failed")
    changed = sum(1 for item in items.values() if (item.get("field_updates") or 0) > 0)
    summary = {
        "total_candidates": len(candidates),
        "processed": succeeded + failed,
        "remaining": len(candidates) - succeeded - failed,
        "succeeded": succeeded,
        "failed": failed,
        "tenders_covered": succeeded + failed,
        "tenders_with_fields_filled": changed,
        "documents_inserted": stats["documents_inserted"],
        "sections_inserted": stats["sections_inserted"],
        "field_updates": stats["field_updates"],
        "characters_added": stats["characters_added"],
    }
    save_state(state)
    print(json.dumps(summary, ensure_ascii=False), flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--max-attempts", type=int, default=MAX_ATTEMPTS)
    parser.add_argument("--limit", type=int, default=0, help="process only the first N candidates")
    parser.add_argument("--batch", type=int, default=BATCH_SIZE,
                        help="candidates per scheduling batch")
    args = parser.parse_args()

    try:
        fd = os.open(LOCK_FILE, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        print("[SKIP] another portal document worker is already active", flush=True)
        return
    with os.fdopen(fd, "w") as handle:
        handle.write(str(os.getpid()))

    candidates = build_candidates()
    if args.limit:
        candidates = candidates[: args.limit]
    state = load_state()
    active = {candidate["reference"] for candidate in candidates}
    state["items"] = {ref: item for ref, item in state["items"].items() if ref in active}
    state["stats"]["candidates"] = len(candidates)
    print(json.dumps({"event": "start", "candidates": len(candidates),
                      "workers": args.workers}), flush=True)
    stop = threading.Event()

    def heartbeat():
        while not stop.wait(275):
            try:
                report(state, candidates)
            except Exception as exc:  # noqa: BLE001
                print(json.dumps({"event": "heartbeat_error",
                                  "reason": type(exc).__name__}), flush=True)

    monitor = threading.Thread(target=heartbeat, daemon=True)
    monitor.start()
    try:
        while True:
            pending = []
            for candidate in candidates:
                item = state["items"].get(candidate["reference"], {})
                if item.get("status") == "done":
                    continue
                if item.get("status") == "failed" and item.get("attempts", 0) >= args.max_attempts:
                    continue
                pending.append(candidate)
            if not pending:
                break
            if args.batch:
                pending = pending[: args.batch]

            print(json.dumps({"event": "batch", "pending": len(pending),
                              "remaining": len(candidates) - sum(
                                  1 for item in state["items"].values()
                                  if item.get("status") in ("done", "failed"))}),
                  flush=True)
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                futures = {pool.submit(process_candidate, c): c for c in pending}
                for future in as_completed(futures):
                    candidate = futures[future]
                    ref = candidate["reference"]
                    try:
                        result = future.result()
                    except Exception as exc:  # noqa: BLE001
                        result = {"error": f"{type(exc).__name__}: {exc}"[:240],
                                  "documents_inserted": 0, "sections_inserted": 0,
                                  "field_updates": 0, "characters_added": 0}
                    item = state["items"].setdefault(ref, {"attempts": 0})
                    item["attempts"] = int(item.get("attempts", 0)) + 1
                    item["last_attempt"] = now_iso()
                    if result.get("error"):
                        item["status"] = ("failed" if item["attempts"] >= args.max_attempts
                                          else "error")
                        item["error"] = result["error"]
                        if item["status"] == "failed":
                            state["stats"]["failed"] += 1
                    else:
                        item["status"] = "done"
                        item["error"] = None
                        item["field_updates"] = result["field_updates"]
                        state["stats"]["succeeded"] += 1
                        for key in ("documents_inserted", "sections_inserted",
                                    "field_updates", "characters_added"):
                            state["stats"][key] += int(result.get(key) or 0)
                    save_state(state)

            report(state, candidates)
        report(state, candidates)
        print("[DONE] portal document collection finished", flush=True)
    finally:
        stop.set()
        monitor.join(timeout=3)
        if db_cps._POOL is not None:
            db_cps._POOL.close()
        LOCK_FILE.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
