"""Collecte exhaustive des documents publics des appels d'offres.

RÈGLE PRODUIT : aucun utilisateur ne choisit un nombre de documents.
`_BATCH_SIZE` est un découpage mémoire interne ; la file est drainée jusqu'à
épuisement. Chaque URL canonique n'est téléchargée qu'une fois, même si
plusieurs références la partagent. Les échecs restent en attente avec backoff.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from html import unescape
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urljoin, urlsplit

import requests

import cps_ingest
import db_cps
from scrape_portal import BASE, TIMEOUT, UA, canonical_url
from storage import make_uploader

MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024
MAX_LINKS = 12                     # garde-fou technique interne, pas un quota
_BATCH_SIZE = 200                  # chunk mémoire interne, PAS une limite métier
_IMMEDIATE_RETRIES = 2
_BACKOFF_HOURS = (1, 2, 4, 8, 16, 24)
_MAX_LOOPS = 10000                 # filet anti-boucle, jamais exposé

_MARKERS = re.compile(r"\.pdf\b|\.zip\b|download|telecharg|télécharg|\bcps\b|\bdce\b|additif|annexe", re.I)


class DocumentLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            attributes = dict(attrs)
            self.current = [attributes.get("href") or "", attributes.get("title") or ""]

    def handle_data(self, data):
        if self.current is not None:
            self.current[1] += " " + data

    def handle_endtag(self, tag):
        if tag == "a" and self.current is not None:
            self.links.append(self.current)
            self.current = None


def portal_url(base: str, href: str) -> str | None:
    url = urljoin(base, unescape(href))
    parts = urlsplit(url)
    if (parts.scheme == "https" and parts.hostname in
            ("marchespublics.gov.ma", "www.marchespublics.gov.ma") and
            parts.port in (None, 443) and not parts.username and not parts.password):
        return parts._replace(fragment="").geturl()
    return None


def get_bytes(session, url: str, limit: int) -> tuple[str, bytes]:
    for _ in range(4):
        with session.get(url, timeout=(8, TIMEOUT), stream=True, allow_redirects=False) as response:
            if response.is_redirect:
                target = portal_url(url, response.headers["Location"])
                if not target:
                    raise ValueError("redirection hors portail")
                url = target
                continue
            response.raise_for_status()
            data = bytearray()
            for chunk in response.iter_content(64 * 1024):
                data.extend(chunk)
                if len(data) > limit:
                    raise ValueError("fichier trop volumineux")
            return url, bytes(data)
    raise ValueError("trop de redirections")


def is_pdf_entry(entry) -> bool:
    path = PurePosixPath(entry.filename)
    return (not entry.is_dir() and path.suffix.lower() == ".pdf"
            and "__MACOSX" not in path.parts and not path.name.startswith("._"))


def pdf_files(url: str, data: bytes):
    if data.startswith(b"%PDF-"):
        name = PurePosixPath(unquote(urlsplit(url).path)).name
        yield name if name.lower().endswith(".pdf") else "document.pdf", data
    elif data.startswith(b"PK"):
        from zipfile import ZipFile
        with ZipFile(io.BytesIO(data)) as archive:
            budget = MAX_DOWNLOAD_BYTES
            for entry in archive.infolist():
                if not is_pdf_entry(entry):
                    continue
                if entry.file_size > min(budget, cps_ingest.MAX_PDF_BYTES):
                    continue
                budget -= entry.file_size
                pdf = archive.read(entry)
                if pdf.startswith(b"%PDF-"):
                    yield PurePosixPath(entry.filename).name, pdf


def _merge_signals(current: dict, candidate: dict) -> dict:
    """Garde le signal le plus riche, sans jamais inventer de valeur."""
    if not candidate:
        return current
    if not current:
        return candidate
    score = lambda s: (len(s.get("signals") or []) * 10 + int(s.get("text_length") or 0))
    return candidate if score(candidate) > score(current) else current


def _fetch_with_retries(session, url: str, limit: int) -> tuple[str, bytes]:
    last = None
    for tentative in range(_IMMEDIATE_RETRIES + 1):
        try:
            return get_bytes(session, url, limit)
        except Exception as exc:                    # noqa: BLE001
            last = exc
            if tentative < _IMMEDIATE_RETRIES:
                time.sleep(0.4 * (tentative + 1))
    raise last if last else RuntimeError("téléchargement impossible")


def collect_tender(session, tender: dict, uploader) -> dict:
    detail_url = portal_url(BASE, tender["source_url"])
    if not detail_url:
        return {"saved": 0, "signals": {}, "error": "hors portail"}

    try:
        detail_url, html = _fetch_with_retries(session, detail_url, 3 * 1024 * 1024)
    except Exception as exc:                        # noqa: BLE001
        return {"saved": 0, "signals": {}, "error": f"detail: {type(exc).__name__}"}

    parser = DocumentLinks()
    parser.feed(html.decode("utf-8", errors="replace"))
    links = {}
    for href, label in parser.links:
        if href and not href.startswith("#") and _MARKERS.search(unquote(href) + " " + label):
            url = portal_url(detail_url, href)
            if url and url != detail_url:
                links.setdefault(url, label)

    saved = 0
    originals = 0
    signals: dict = {}
    errors: list[str] = []
    for url, label in list(links.items())[:MAX_LINKS]:
        try:
            response_url, data = _fetch_with_retries(session, url, MAX_DOWNLOAD_BYTES)
            if data.startswith(b"PK"):
                from enrich_tender_documents import _store_original

                archive_name = Path(PurePosixPath(urlsplit(response_url).path).name or "document").with_suffix(".zip")
                try:
                    original = _store_original(tender["reference"], response_url, archive_name, data)
                    originals += int(original["status"] == "stored")
                except Exception as exc:
                    errors.append(f"archive:{type(exc).__name__}")
            for name, pdf in pdf_files(response_url, data):
                descriptor = (name + " " + label + " " + response_url).lower()
                doc_type = "ADDITIF" if re.search(r"additif|rectificatif|avenant", descriptor) else (
                    "CPS" if re.search(r"\bcps\b|prescriptions sp", descriptor) else "DCE"
                )
                result = cps_ingest.ingest_cps(
                    tender["reference"], pdf, source_url=response_url, doc_type=doc_type,
                    filename=name, storage_uploader=uploader,
                )
                if result["status"] == "extracted" or result.get("reason") == "already_ingested":
                    saved += 1
                    signals = _merge_signals(signals, result.get("signals") or {})
                else:
                    errors.append(f"{result['status']}:{result.get('reason', '')}")
        except Exception as exc:                    # noqa: BLE001
            errors.append(type(exc).__name__)

    form = any("entreprisedemandetelechargementdce" in url.lower() for url in links)
    error = "dce_form" if form else (None if saved or not errors else "; ".join(errors[:3]))
    return {"saved": saved, "originals": originals, "signals": signals, "error": error}


def _fetch_one(tender: dict, uploader) -> tuple[str, dict]:
    with requests.Session() as session:
        session.headers.update(UA)
        try:
            return tender["reference"], collect_tender(session, tender, uploader)
        except Exception as exc:                    # noqa: BLE001
            return tender["reference"], {"saved": 0, "signals": {},
                                          "error": f"annonce: {type(exc).__name__}: {exc}"[:240]}


def _pending(company: str, date_cible: str, *, all_tenders: bool,
             batch_size: int) -> list[dict]:
    """File d'enrichissement : une ligne = une URL canonique à traiter."""
    common = (
        "FROM tenders t "
        "WHERE t.statut = 'ouvert' AND t.offer_type IS NOT NULL "
        "  AND t.source_url IS NOT NULL AND t.source_url <> '' "
        "  AND (t.date_remise IS NULL OR t.date_remise >= %s::date) "
        "  AND ("
        "    (t.enriched_at IS NULL "
        "     AND (t.enrich_next_at IS NULL OR t.enrich_next_at <= now())) "
        "    OR (t.enriched_at IS NOT NULL AND t.enrich_next_at IS NOT NULL "
        "        AND t.enrich_next_at <= now()) "
        "  ) "
        "  AND NOT EXISTS (SELECT 1 FROM tender_documents d "
        "                  WHERE d.reference = t.reference AND d.statut <> 'missing_cps') "
    )
    if all_tenders:
        sql = (
            "SELECT t.reference, t.source_url, t.url_key, t.enrich_attempts " + common +
            "ORDER BY (t.date_collecte = %s::date) DESC, t.enrich_next_at NULLS FIRST, t.date_remise NULLS LAST, t.reference "
            "LIMIT %s"
        )
        return db_cps.query(sql, (date_cible, date_cible, batch_size))

    sql = (
        "SELECT t.reference, t.source_url, t.url_key, t.enrich_attempts " + common +
        "  AND EXISTS (SELECT 1 FROM scores s WHERE s.reference = t.reference "
        "              AND s.company_id = %s AND s.calcule_le::date = %s) "
        "ORDER BY t.enrich_next_at NULLS FIRST, t.date_remise NULLS LAST, t.reference "
        "LIMIT %s"
    )
    return db_cps.query(sql, (date_cible, company, date_cible, batch_size))


def _mark(reference: str, result: dict) -> None:
    import time as _time

    def _exec(sql, params):
        for tentative in range(3):
            try:
                return db_cps.execute(sql, params)
            except Exception as exc:  # noqa: BLE001
                if tentative == 2:
                    raise
                _time.sleep(1.0 * (tentative + 1))

    signals = result.get("signals") or {}
    if not result.get("error"):
        _exec(
            """
            UPDATE tenders
            SET enriched_at = now(), enrich_attempts = 0,
                enrich_next_at = NULL, enrich_error = NULL,
                extraction = extraction || %s::jsonb
            WHERE reference = %s
            """,
            (json.dumps(signals, ensure_ascii=False), reference),
        )
        return

    tentatives = int(result.get("attempts") or 0) + 1
    heures = _BACKOFF_HOURS[min(tentatives - 1, len(_BACKOFF_HOURS) - 1)]
    _exec(
        """
        UPDATE tenders
        SET enrich_attempts = %s,
            enrich_next_at = now() + make_interval(hours => %s),
            enrich_error = %s
        WHERE reference = %s
        """,
        (tentatives, heures, str(result["error"])[:240], reference),
    )


def run_documents(date_cible: str, company: str, *, batch_size: int = _BATCH_SIZE,
                  workers: int = 8, all_tenders: bool = True,
                  time_budget: float | None = None) -> dict:
    """Draine TOUTE la file de documents. Aucune limite de nombre exposée."""
    uploader = make_uploader()
    if not uploader:
        return {"documents_ingerees": 0, "documents_annonces": 0,
                "urls_uniques": 0, "passes": 0, "source_documents": "storage_indisponible"}

    total_docs = 0
    total_originals = 0
    total_annonces = 0
    total_urls = 0
    passes = 0
    failed = 0
    portal_unavailable = False
    started = time.monotonic()

    while passes < _MAX_LOOPS and (time_budget is None or time.monotonic() - started < time_budget):
        rows = _pending(company, date_cible, all_tenders=all_tenders,
                        batch_size=max(1, batch_size))
        if not rows:
            break
        passes += 1

        groupes: dict[str, list[dict]] = {}
        for row in rows:
            key = row.get("url_key") or canonical_url(row["source_url"]) or row["source_url"]
            groupes.setdefault(key, []).append(row)

        # Une seule session par URL canonique ; parallélisme entre URL distinctes.
        detail_failures = 0
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {
                pool.submit(_fetch_one, groupe[0], uploader): groupe
                for groupe in groupes.values()
            }
            for future in as_completed(futures):
                groupe = futures[future]
                reference, result = future.result()
                total_originals += result.get("originals", 0)
                if (result.get("error") or "").startswith("detail:"):
                    detail_failures += 1
                for tender in groupe:
                    _mark(tender["reference"], {**result, "attempts": tender.get("enrich_attempts")})
                    if not result.get("error"):
                        total_docs += int(result.get("saved") or 0)
                        total_annonces += 1
                    else:
                        failed += 1
                total_urls += 1
        if time_budget is not None and detail_failures == len(groupes):
            portal_unavailable = True
            break

    return {
        "documents_ingerees": total_docs,
        "documents_originaux": total_originals,
        "documents_annonces": total_annonces,
        "urls_uniques": total_urls,
        "passes": passes,
        "documents_retry_scheduled": failed,
        "source_documents": "portail_indisponible" if portal_unavailable else "portail",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("date")
    parser.add_argument("company")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    resultat = run_documents(args.date, args.company, workers=args.workers)
    if resultat["source_documents"] == "storage_indisponible":
        print("Documents à vérifier : Supabase Storage non configuré")
        return
    from enrich_tender_documents import refresh_open_tenders

    refresh_open_tenders(args.workers, args.date)
    print(f"TOTAL documents ingérés : {resultat['documents_ingerees']} "
          f"sur {resultat['documents_annonces']} annonces "
          f"({resultat['urls_uniques']} URLs, {resultat['passes']} passes)")


if __name__ == "__main__":
    main()
