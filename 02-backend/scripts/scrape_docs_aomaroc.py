# =====================================================================
# scrape_docs_aomaroc.py — Documents (DCE/CPS) via le relais aomaroc.com
# quand le portail officiel est indisponible. L'alignement est direct :
# les tenders en base portent une source_url portail avec refConsultation
# + orgAcronyme, et aomaroc expose exactement les mêmes clés.
#
# Flux par tender :
#   1) lit les tenders sans document ingéré (idempotent)
#   2) POST aomaroc /cps/lancer?ref={refConsultation}&org={orgAcronyme}
#   3) poll GET /cps/etat?id= jusqu'à fini/erreur
#   4) télécharge /cps/fichier?id= (ZIP du DCE), extrait les PDF
#   5) ingest chaque PDF via cps_ingest (CPS/DCE/AVIS/ADDITIF) :
#      upload Storage + extraction texte + sections + tender_documents
#
# Idempotent : un tender déjà 'extracted'/'ready' est sauté ; les échecs
# ('echec'/'missing_cps') sont retrés à la prochaine exécution. Le
# dédoublonnage exact de fichier est assuré par l'UNIQUE sha256 en base.
#
# Usage :
#   python scripts/scrape_docs_aomaroc.py --limit 10
#   python scripts/scrape_docs_aomaroc.py --reference "portal:03/2026/CTL"
#   python scripts/scrape_docs_aomaroc.py --dry-run --limit 20
# =====================================================================
from __future__ import annotations

import argparse
import io
import re
import sys
import time
import unicodedata
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from urllib.parse import parse_qs, urlencode, urlsplit

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from soukna_graph import config, db
from soukna_graph.tools import cps_ingest, storage

AO_BASE = "https://www.aomaroc.com"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; SouknaBot/1.0)",
      "Referer": AO_BASE + "/"}

# Étapes du job aomaroc (cf. /cps JS : attente|connexion|formulaire|
# telechargement|fini|erreur)
POLL_INTERVAL_S = 4.0
POLL_TIMEOUT_S = 180.0          # portail lent : on laisse jusqu'à 3 min
JOB_RETRY = 1                   # 1 relance si 'erreur'
MAX_ZIP_BYTES = 80 * 1024 * 1024
MAX_DOCS_PER_TENDER = 12        # au plus N PDF ingérés par dossier DCE

# Classification du nom de fichier -> doc_type (contrainte DB :
# CPS|DCE|AVIS|ADDITIF|PV). Ordre = priorité de détection.
_DOC_TYPE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("ADDITIF", re.compile(r"additif|rectificatif|avenant", re.I)),
    ("CPS", re.compile(r"\bc\.?p\.?s\b|cahier\s+des\s+(prescriptions|charges)", re.I)),
    ("AVIS", re.compile(r"\bavis\b", re.I)),
    ("DCE", re.compile(r"\brc\b|reglement|règlement", re.I)),
]
_DOC_PRIORITY = {"CPS": 0, "DCE": 1, "ADDITIF": 2, "AVIS": 3}


def classify_doc_type(filename: str) -> str:
    name = PurePosixPath(filename).stem
    for doc_type, rx in _DOC_TYPE_RULES:
        if rx.search(name):
            return doc_type
    return "DCE"


def sanitize_path_part(name: str, max_len: int = 120) -> str:
    """Nom de fichier sûr pour Supabase Storage (1 seul niveau, ASCII).

    Translittère les accents (é->e) : le Storage rejette certains chemins
    non-ASCII ("storage_upload_failed" observé sur des noms accentués).
    """
    cleaned = unicodedata.normalize("NFKD", name)
    cleaned = "".join(c for c in cleaned if not unicodedata.combining(c))
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = re.sub(r"[^\w.\-]+", "", cleaned, flags=re.ASCII)
    return cleaned[:max_len] or "document.pdf"


def parse_portal_keys(source_url: str) -> tuple[str, str] | None:
    """Extrait (refConsultation, orgAcronyme) d'une source_url portail."""
    if not source_url or "refConsultation" not in source_url:
        return None
    try:
        qs = parse_qs(urlsplit(source_url).query)
    except ValueError:
        return None
    ref = (qs.get("refConsultation") or [""])[0].strip()
    org = (qs.get("orgAcronyme") or [""])[0].strip()
    if not ref or not org:
        return None
    return ref, org


def launch_job(session: requests.Session, ref: str, org: str) -> str | None:
    """POST /cps/lancer -> id de job (file d'attente aomaroc)."""
    url = f"{AO_BASE}/cps/lancer?{urlencode({'ref': ref, 'org': org})}"
    r = session.post(url, timeout=60)
    if r.status_code != 200:
        return None
    return (r.json() or {}).get("id")


def poll_job(session: requests.Session, job_id: str,
             timeout_s: float = POLL_TIMEOUT_S) -> dict:
    """Poll /cps/etat jusqu'à fini/erreur (ou timeout -> {'etape': 'timeout'})."""
    deadline = time.monotonic() + timeout_s
    url = f"{AO_BASE}/cps/etat?{urlencode({'id': job_id})}"
    while time.monotonic() < deadline:
        try:
            r = session.get(url, timeout=30)
            st = r.json() if r.status_code == 200 else {}
        except requests.RequestException:
            st = {}
        etape = st.get("etape")
        if etape in ("fini", "erreur"):
            return st
        time.sleep(POLL_INTERVAL_S)
    return {"etape": "timeout", "err": "poll_timeout"}


def fetch_zip(session: requests.Session, job_id: str) -> bytes | None:
    """Télécharge /cps/fichier?id= (ZIP du DCE complet)."""
    url = f"{AO_BASE}/cps/fichier?{urlencode({'id': job_id})}"
    try:
        r = session.get(url, timeout=180, stream=True)
    except requests.RequestException:
        return None
    if r.status_code != 200:
        return None
    chunks = []
    total = 0
    for chunk in r.iter_content(chunk_size=256 * 1024):
        chunks.append(chunk)
        total += len(chunk)
        if total > MAX_ZIP_BYTES:
            return None
    return b"".join(chunks)


def make_session() -> requests.Session:
    """Session aomaroc (UA navigateur + referer) pour le relais CPS."""
    s = requests.Session()
    s.headers.update(UA)
    return s


def pdfs_from_zip(zip_bytes: bytes, _depth: int = 0,
                  _seen_sha: set[str] | None = None) -> list[tuple[str, bytes]]:
    """PDFs du ZIP du DCE, triés : CPS d'abord, puis DCE/ADDITIF/AVIS.

    Récursif (profondeur 2) : certains acheteurs livrent le DCE sous forme
    de ZIP imbriqué dans le ZIP retourné par le portail. Dédupliqué par
    sha256 (un même PDF peut apparaître dans le ZIP racine ET imbriqué).
    """
    import hashlib
    seen_sha = _seen_sha if _seen_sha is not None else set()
    out = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return out
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = PurePosixPath(info.filename).name  # ignore sous-dossiers
        if (name.lower().endswith(".zip") and _depth < 2
                and 0 < info.file_size <= MAX_ZIP_BYTES):
            out.extend(pdfs_from_zip(zf.read(info), _depth + 1, seen_sha))
            continue
        if not name.lower().endswith(".pdf"):
            continue
        if info.file_size < 1024:  # PDF vide/corrompu
            continue
        data = zf.read(info)
        if not data.startswith(b"%PDF"):
            continue
        sha = hashlib.sha256(data).hexdigest()
        if sha in seen_sha:
            continue
        seen_sha.add(sha)
        out.append((name, data))
    out.sort(key=lambda nd: (_DOC_PRIORITY.get(classify_doc_type(nd[0]), 9),
                             -len(nd[1])))
    return out


def record_failure(reference: str, source_url: str, statut: str,
                   raison: str) -> None:
    """Trace un échec/absence dans tender_documents (retrier plus tard)."""
    import hashlib
    fake_sha = hashlib.sha256(f"{reference}|{statut}|{raison}".encode()).hexdigest()
    try:
        db.tender_document_create(
            reference=reference,
            storage_path=f"{reference.replace('/', '_')}/(absent)",
            sha256=fake_sha,
            doc_type=None, mime=None, size_bytes=None, pages=None,
            extraction=None, extracted_text=None,
            source_url=source_url or None,
            statut=statut, echec_raison=raison,
            sections=0, char_count=0,
            downloaded_at=datetime.now(timezone.utc),
        )
    except Exception as exc:
        print(f"    WARN: trace echec impossible pour {reference}: {exc}", flush=True)


def process_tender(tender: dict, session: requests.Session,
                   uploader) -> dict:
    ref = tender["reference"]
    keys = parse_portal_keys(tender.get("source_url") or "")
    if not keys:
        return {"reference": ref, "status": "skipped", "reason": "no_portal_keys"}

    # Idempotence tender : déjà ingéré -> sauter
    doc = db.tender_document_by_reference(ref)
    if doc and doc.get("statut") in ("extracted", "ready"):
        return {"reference": ref, "status": "skipped", "reason": "already_ingested"}

    refc, org = keys
    ao_cps_url = f"{AO_BASE}/cps?ref={refc}&org={org}"

    # 1..2) lancer + poller le job (1 relance en cas d'erreur)
    status: dict = {}
    job_id = None
    for attempt in range(1 + JOB_RETRY):
        try:
            job_id = launch_job(session, refc, org)
        except requests.RequestException as exc:
            job_id = None
            status = {"etape": "erreur", "err": f"lancer_failed: {str(exc)[:120]}"}
        if job_id:
            status = poll_job(session, job_id)
            if status.get("etape") == "fini":
                break
        time.sleep(3)
    if status.get("etape") != "fini" or not job_id:
        raison = f"aomaroc_job:{status.get('etape')}:{status.get('err') or ''}"[:200]
        record_failure(ref, ao_cps_url, "echec", raison)
        return {"reference": ref, "status": "echec", "reason": raison}

    # 3) ZIP du DCE
    zip_bytes = fetch_zip(session, job_id)
    if not zip_bytes:
        record_failure(ref, ao_cps_url, "echec", "zip_download_failed")
        return {"reference": ref, "status": "echec", "reason": "zip_download_failed"}

    # 4) PDFs + ingestion (CPS en premier)
    pdfs = pdfs_from_zip(zip_bytes)[:MAX_DOCS_PER_TENDER]
    if not pdfs:
        record_failure(ref, ao_cps_url, "missing_cps", "no_pdf_in_dce_zip")
        return {"reference": ref, "status": "missing_cps", "reason": "no_pdf_in_dce_zip"}

    ref_dir = sanitize_path_part(ref.replace("/", "_"))
    ingested = []
    for name, data in pdfs:
        doc_type = classify_doc_type(name)
        fname = sanitize_path_part(name)
        res = cps_ingest.ingest_cps(
            ref, data,
            source_url=ao_cps_url,
            doc_type=doc_type,
            filename=fname,
            storage_path=f"{ref_dir}/{fname}",
            storage_uploader=uploader,
            idempotent=False,  # plusieurs pièces pour un même tender
        )
        ingested.append({"doc_type": doc_type, "filename": fname,
                         "status": res.get("status"),
                         "reason": res.get("reason")})

    ok = [d for d in ingested if d["status"] == "extracted"]
    if not ok:
        record_failure(ref, ao_cps_url, "echec",
                       "no_pdf_extracted:" + str(ingested[0].get("reason", ""))[:120])
        return {"reference": ref, "status": "echec", "reason": "no_pdf_extracted",
                "documents": ingested}
    return {"reference": ref, "status": "ok", "documents": ingested}


def load_tenders(limit: int, reference: str | None) -> list[dict]:
    if reference:
        t = db.tenders_get(reference)
        return [t] if t else []
    # Sans document ingéré : deadline à venir la plus proche d'abord
    # (offres ouvertes), puis les expirées/sans date et les plus récentes.
    return db.query(
        """
        SELECT t.* FROM tenders t
        WHERE t.source_url LIKE '%%refConsultation=%%'
          AND t.source_url LIKE '%%orgAcronyme=%%'
          AND NOT EXISTS (
              SELECT 1 FROM tender_documents d
              WHERE d.reference = t.reference
                AND d.statut IN ('extracted', 'ready'))
        ORDER BY (t.date_remise IS NULL OR t.date_remise < CURRENT_DATE),
                 t.date_remise NULLS LAST, t.cree_le DESC
        LIMIT %s
        """,
        (limit,),
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--reference", default=None,
                    help="Traiter un seul tender (ex. portal:03/2026/CTL)")
    ap.add_argument("--poll-timeout", type=float, default=POLL_TIMEOUT_S)
    ap.add_argument("--sleep", type=float, default=3.0,
                    help="Pause entre deux tenders (politesse aomaroc)")
    ap.add_argument("--no-upload", action="store_true",
                    help="Désactiver l'upload Supabase Storage")
    ap.add_argument("--dry-run", action="store_true",
                    help="Lister les tenders cibles sans rien télécharger")
    args = ap.parse_args()

    tenders = load_tenders(args.limit, args.reference)
    print(f"{len(tenders)} tender(s) à traiter", flush=True)
    if args.dry_run:
        for t in tenders:
            keys = parse_portal_keys(t.get("source_url") or "")
            print(f"  {t['reference']} | {t.get('date_remise')} | ref={keys[0] if keys else '?'} org={keys[1] if keys else '?'}", flush=True)
        return 0

    uploader = None if args.no_upload else storage.make_uploader()
    if uploader is None:
        print("WARNING: storage_uploader indisponible (SUPABASE_URL/SERVICE_KEY) "
              "-> upload désactivé", flush=True)

    session = make_session()

    stats = {"processed": 0, "ok": 0, "skipped": 0, "echec": 0, "missing": 0}
    for t in tenders:
        try:
            res = process_tender(t, session, uploader)
        except Exception as exc:
            res = {"reference": t["reference"], "status": "echec",
                   "reason": f"unexpected: {str(exc)[:150]}"}
        st = res["status"]
        stats[{"ok": "ok", "skipped": "skipped", "missing_cps": "missing"}.get(st, "echec")] += 1
        stats["processed"] += 1
        docs = res.get("documents")
        print(f"[{stats['processed']}] {res['reference']}: {st} "
              f"{res.get('reason') or (docs if docs else '')}", flush=True)
        time.sleep(args.sleep)

    print("STATS:", stats, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
