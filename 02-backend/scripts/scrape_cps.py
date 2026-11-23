# =====================================================================
# scrape_cps.py — Collecte des PDF CPS des offres (tenders) :
#   1) lit les tenders avec URL de détail portail et sans CPS ingéré
#   2) récupère la page de détail, extrait les liens PDF
#   3) télécharge chaque PDF (garde-fous taille/pages)
#   4) upload dans Supabase Storage 'cps-originaux' (service_role)
#   5) extrait texte + sections (pypdf/OCR)
#   6) écrit tender_documents + cps_sections via cps_ingest
#
# Idempotent : un tender déjà 'extracted'/'ready' est sauté.
# Usage :
#   python scripts/scrape_cps.py --limit 5
#   python scripts/scrape_cps.py --reference "portal:43/2026"
# =====================================================================
from __future__ import annotations

import argparse
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import config, db
from app.tools import cps_extract, cps_ingest, storage

UA = {"User-Agent": "Mozilla/5.0 (compatible; SouknaBot/1.0; +https://soukna.ma)"}

# Mots-clés de nom de fichier / lien téléchargeable
_PDF_HINT = re.compile(r"\.pdf(\?|$)|\b(telecharg|download|document|fichier|piece|caps|cpv|cps)\b",
                       re.IGNORECASE)


def find_pdf_links(html: str, base_url: str) -> list[str]:
    links = []
    for m in re.finditer(r'<a\b[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.S | re.I):
        href, label = m.group(1), re.sub(r"<[^>]+>", " ", m.group(2)).strip()
        if not href or href.startswith("javascript"):
            continue
        if _PDF_HINT.search(href) or _PDF_HINT.search(label):
            links.append(urljoin(base_url, href))
    # dédoublonner en gardant l'ordre
    seen, out = set(), []
    for u in links:
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def download_pdf(url: str) -> bytes | None:
    try:
        r = requests.get(url, headers=UA, timeout=config.PORTAL_TIMEOUT_S)
        if r.status_code != 200:
            return None
        ctype = r.headers.get("Content-Type", "")
        if "pdf" not in ctype.lower() and not r.content[:4] == b"%PDF":
            return None
        return r.content
    except requests.RequestException:
        return None


def process_tender(tender: dict, uploader) -> dict:
    ref = tender["reference"]
    url = tender.get("source_url") or ""
    if not url or "refConsultation" not in url:
        return {"reference": ref, "status": "skipped", "reason": "no_detail_url"}
    # idempotence
    doc = db.tender_document_by_reference(ref)
    if doc and doc.get("statut") in ("extracted", "ready"):
        return {"reference": ref, "status": "skipped", "reason": "already_ingested"}
    try:
        r = requests.get(url, headers=UA, timeout=config.PORTAL_TIMEOUT_S)
        r.raise_for_status()
    except requests.RequestException as exc:
        return {"reference": ref, "status": "echec", "reason": "detail_fetch_failed",
                "error": str(exc)[:200]}
    links = find_pdf_links(r.text, url)
    if not links:
        return {"reference": ref, "status": "missing_cps", "reason": "no_pdf_link_found"}
    out = []
    for i, pdf_url in enumerate(links[:3]):  # au plus 3 documents par AO
        data = download_pdf(pdf_url)
        if not data:
            continue
        res = cps_ingest.ingest_cps(
            ref, data,
            source_url=pdf_url,
            doc_type="CPS",
            filename=f"doc{i+1}.pdf",
            storage_path=f"{ref.replace('/', '_')}/doc{i+1}.pdf",
            storage_uploader=uploader,
        )
        out.append(res)
    if not out:
        return {"reference": ref, "status": "echec", "reason": "no_pdf_downloaded"}
    return {"reference": ref, "status": "ok", "documents": out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--reference", default=None)
    args = ap.parse_args()

    uploader = storage.make_uploader()  # None si credentials absents
    if uploader is None:
        print("WARNING: storage_uploader indisponible (SUPABASE_URL/SERVICE_KEY) "
              "-> upload désactivé", flush=True)

    if args.reference:
        tenders = [db.tenders_get(args.reference)]
        tenders = [t for t in tenders if t]
    else:
        tenders = db.query(
            "SELECT * FROM tenders WHERE source_url LIKE '%refConsultation%' "
            "ORDER BY cree_le DESC LIMIT %s", (args.limit,))

    stats = {"processed": 0, "ok": 0, "skipped": 0, "echec": 0, "missing": 0}
    for t in tenders:
        res = process_tender(t, uploader)
        st = res["status"]
        if st == "ok": stats["ok"] += 1
        elif st == "skipped": stats["skipped"] += 1
        elif st == "missing_cps": stats["missing"] += 1
        else: stats["echec"] += 1
        stats["processed"] += 1
        print(f"[{stats['processed']}] {res['reference']}: {st} "
              f"{res.get('reason') or res.get('documents','')}", flush=True)
        time.sleep(1.0)  # politesse portail

    print("STATS:", stats, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
PYEOF