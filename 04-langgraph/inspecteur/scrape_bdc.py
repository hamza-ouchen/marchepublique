"""Import purchase notices from the portal's separate public listing."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from urllib.parse import urljoin, urlsplit
from zoneinfo import ZoneInfo
import re

import requests
from bs4 import BeautifulSoup

import db_cps
import scrape_portal

LISTING = f"{scrape_portal.BASE}/bdc/entreprise/consultation/"
HOST = urlsplit(LISTING).hostname


def _read(url):
    response = requests.get(url, headers=scrape_portal.UA, timeout=25)
    response.raise_for_status()
    return BeautifulSoup(response.content, "html.parser")


def _details(record):
    url, notice_id, reference, title, deadline = record
    page = _read(url)
    if any(label.strip().casefold() in {"annulé", "annulée"} for label in page.stripped_strings):
        return None
    fields = {}
    for label in page.select("span.font-bold, span.fw-bold"):
        value = label.find_next_sibling("span")
        if value:
            fields[label.get_text(strip=True).casefold()] = value.get_text(" ", strip=True)
    publication = fields.get("date mise en ligne", "")
    try:
        published_at = datetime.strptime(publication, "%d/%m/%Y %H:%M")
        publication = published_at.date().isoformat()
        heure_publication = published_at.time().isoformat(timespec="minutes")
    except ValueError:
        publication = heure_publication = None
    official_deadline = fields.get("date limite de réception des devis", "")
    try:
        deadline = datetime.strptime(official_deadline, "%d/%m/%Y %H:%M")
    except ValueError:
        pass
    if deadline <= datetime.now(ZoneInfo("Africa/Casablanca")).replace(tzinfo=None):
        return None
    buyer = fields.get("acheteur public")
    if not buyer:
        raise ValueError("Missing purchaser in purchase-notice detail")
    return {
        "source_ref": f"{reference} [bdc:{notice_id}]",
        "url": url,
        "title": title,
        "buyer": buyer,
        "city": fields.get("lieu d'exécution") or fields.get("lieu d’exécution"),
        "sector": fields.get("catégorie principale", "autre"),
        "date_publication": publication,
        "heure_publication": heure_publication,
        "deadline": deadline.date().isoformat(),
        "heure_remise": deadline.time().isoformat(timespec="minutes"),
        "offer_type": "bon_de_commande",
    }


def collect_purchase_notices(date_cible, workers):
    known = {row["source_url"] for row in db_cps.query(
        "SELECT source_url FROM tenders WHERE offer_type='bon_de_commande'"
    )}
    entries, visited = {}, set()
    now = datetime.now(ZoneInfo("Africa/Casablanca")).replace(tzinfo=None)
    url = LISTING
    while url and url not in visited:
        visited.add(url)
        page = _read(url)
        for card in page.select(".bdc-card"):
            anchor = card.select_one("a[href*='/consultation/show/']")
            if not anchor:
                continue
            detail = urljoin(url, anchor["href"])
            parts = urlsplit(detail)
            identifier = re.fullmatch(r"/bdc/entreprise/consultation/show/(\d+)/?", parts.path)
            if parts.hostname != HOST or not identifier or detail in known:
                continue
            lines = list(card.stripped_strings)
            if any(re.search(r"\bannul[ée]e?s?\b|d[ée]cision d['’]annulation", line, re.I)
                   for line in lines):
                continue
            if len(lines) < 5:
                continue
            day = scrape_portal._parse_deadline(lines[1])
            clock = re.search(r"\d{2}:\d{2}", lines[2])
            if not day or not clock:
                continue
            deadline = datetime.fromisoformat(f"{day}T{clock[0]}")
            if deadline > now:
                entries[identifier[1]] = (detail, identifier[1], lines[3], anchor.get_text(" ", strip=True), deadline)
        next_page = page.find("a", string=lambda label: label and "Suivant" in label)
        url = urljoin(url, next_page["href"]) if next_page and next_page.get("href") else None
        if url and urlsplit(url).hostname != HOST:
            raise ValueError("Unexpected purchase-notice pagination host")
    if url:
        raise RuntimeError("Purchase-notice pagination repeated a page")
    def read_details(record):
        try:
            return _details(record), 0
        except (requests.RequestException, ValueError):
            return None, 1

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        details = list(pool.map(read_details, entries.values()))
    items = [item for item, _ in details if item]
    return {"pages": len(visited), "new": len(items), "details_retry": sum(error for _, error in details),
            "imported": scrape_portal.import_to_db(items, date_cible)}
