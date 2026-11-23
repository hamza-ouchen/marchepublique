# =====================================================================
# scrape_cps_playwright.py — Collecte des PDF CPS via Playwright (navigateur
# réel) avec comportement humain : délais aléatoires, scroll, retry avec
# backoff, contexte persistant (cookies/session PRADO).
#
# Pour chaque tender (URL de détail portail) :
#   1) ouvre la page de détail dans Chromium
#   2) extrait les liens PDF (ancres + iframe + JS)
#   3) télécharge via le contexte navigateur (cookies conservés)
#   4) upload Supabase Storage 'cps-originaux'
#   5) extraction pypdf + sections, écriture tender_documents + cps_sections
#
# Idempotent : un tender déjà extracted/ready est sauté.
#
# Usage :
#   python scripts/scrape_cps_playwright.py --limit 5
#   python scripts/scrape_cps_playwright.py --reference "portal:43/2026"
#   python scripts/scrape_cps_playwright.py --limit 5 --headful
# =====================================================================
from __future__ import annotations

import argparse
import random
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import db
from app.tools import cps_ingest, storage

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36")

_PDF_HINT = re.compile(
    r"\.pdf(\?|$)|\b(telecharg|download|document|fichier|piece|caps|cps|annexe)\b",
    re.IGNORECASE)


def human_pause(lo: float = 0.8, hi: float = 2.0) -> None:
    time.sleep(random.uniform(lo, hi))


def navigate_with_retry(page, url: str, attempts: int = 3) -> bool:
    for i in range(attempts):
        try:
            resp = page.goto(url, wait_until="domcontentloaded", timeout=45000)
            page.wait_for_timeout(random.randint(700, 1500))
            # scroll humain
            page.mouse.wheel(0, random.randint(300, 800))
            human_pause(0.5, 1.2)
            if resp and resp.status >= 500:
                raise RuntimeError(f"HTTP {resp.status}")
            return True
        except Exception as exc:
            print(f"  [retry {i+1}/{attempts}] {url[:70]}... -> {type(exc).__name__}",
                  flush=True)
            if i == attempts - 1:
                return False
            human_pause(4 + i * 3, 8 + i * 4)  # backoff 4-8, 7-11, 10-14 s
    return False


def extract_pdf_links(page, base_url: str) -> list[str]:
    links = set()
    # 1) ancres classiques
    try:
        anchors = page.eval_on_selector_all(
            "a[href]",
            "els => els.map(e => ({href: e.href, text: (e.innerText||'').trim()}))")
        for a in anchors:
            if _PDF_HINT.search(a.get("href", "")) or _PDF_HINT.search(a.get("text", "")):
                if a.get("href", "").startswith("http"):
                    links.add(a["href"])
    except Exception:
        pass
    # 2) iframes / embed / object :
    try:
        srcs = page.eval_on_selector_all(
            "iframe[src], embed[src], object[data]",
            "els => els.map(e => e.src || e.data)")
        for s in srcs:
            if s and (_PDF_HINT.search(s) or ".pdf" in s.lower()):
                links.add(urljoin(base_url, s))
    except Exception:
        pass
    return list(links)


def download_via_context(ctx, url: str) -> bytes | None:
    try:
        resp = ctx.request.get(url, timeout=45000)
        if resp.status != 200:
            return None
        body = resp.body()
        if body[:4] != b"%PDF" and "pdf" not in (resp.headers.get("content-type", "")).lower():
            return None
        return body
    except Exception:
        return None


def process_tender(ctx, page, tender: dict, uploader) -> dict:
    ref = tender["reference"]
    url = tender.get("source_url") or ""
    if not url or "refConsultation" not in url:
        return {"reference": ref, "status": "skipped", "reason": "no_detail_url"}
    doc = db.tender_document_by_reference(ref)
    if doc and doc.get("statut") in ("extracted", "ready"):
        return {"reference": ref, "status": "skipped", "reason": "already_ingested"}

    if not navigate_with_retry(page, url):
        return {"reference": ref, "status": "echec", "reason": "navigation_failed"}

    links = extract_pdf_links(page, url)
    if not links:
        return {"reference": ref, "status": "missing_cps", "reason": "no_pdf_link_found"}

    out = []
    for i, pdf_url in enumerate(links[:3]):
        human_pause(1.0, 2.5)
        data = download_via_context(ctx, pdf_url)
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
        human_pause(1.5, 3.0)

    if not out:
        return {"reference": ref, "status": "echec", "reason": "no_pdf_downloaded"}
    return {"reference": ref, "status": "ok", "documents": out}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=5)
    ap.add_argument("--reference", default=None)
    ap.add_argument("--headful", action="store_true", help="afficher le navigateur")
    ap.add_argument("--persistent", action="store_true",
                    help="contexte persistant (cookies entre runs)")
    args = ap.parse_args()

    uploader = storage.make_uploader()
    if uploader is None:
        print("WARNING: storage_uploader indisponible (SUPABASE_URL/SERVICE_KEY) "
              "-> upload désactivé", flush=True)

    if args.reference:
        tenders = [t for t in [db.tenders_get(args.reference)] if t]
    else:
        tenders = db.query(
            "SELECT * FROM tenders WHERE source_url LIKE '%refConsultation%' "
            "ORDER BY cree_le DESC LIMIT %s", (args.limit,))

    print(f"Tenders à traiter : {len(tenders)}", flush=True)
    stats = {"processed": 0, "ok": 0, "skipped": 0, "echec": 0, "missing": 0}

    with sync_playwright() as p:
        if args.persistent:
            profile = Path(__file__).parent / ".pw_profile"
            ctx = p.chromium.launch_persistent_context(
                str(profile), headless=not args.headful,
                user_agent=UA, locale="fr-FR", viewport={"width": 1366, "height": 900})
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            browser = None
        else:
            browser = p.chromium.launch(headless=not args.headful)
            ctx = browser.new_context(user_agent=UA, locale="fr-FR",
                                      viewport={"width": 1366, "height": 900})
            page = ctx.new_page()

        for t in tenders:
            res = process_tender(ctx, page, t, uploader)
            st = res["status"]
            stats[{"ok":"ok","skipped":"skipped","missing_cps":"missing"}.get(st,"echec")] += 1
            stats["processed"] += 1
            print(f"[{stats['processed']}] {res['reference']}: {st} "
                  f"{res.get('reason') or res.get('documents','')}", flush=True)
            human_pause(2.0, 4.0)  # pause entre tenders

        ctx.close()
        if browser:
            browser.close()

    print("STATS:", stats, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
PYEOF