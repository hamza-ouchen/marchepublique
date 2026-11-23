# =====================================================================
# Téléchargement respectueux des PDF du portail (page de détail d'un avis).
# Aucun LLM. Limites de taille et politesse configurables.
# =====================================================================
from __future__ import annotations

import html as _html
import re
from datetime import date
from typing import Any
from urllib.parse import urljoin

import requests

from . import config

_ANCHOR_RE = re.compile(
    r"<a\b[^>]*?href\s*=\s*[\"']([^\"']+)[\"'][^>]*?>(.*?)</a>",
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")
# Mots qui caractérisent un vrai lien de fichier (pas la navigation du menu).
_FILE_LABELS = ("fichier joint", "telecharger", "télécharger", "cps", "dce",
                "cahier", "prescription", "piece jointe", "pièce jointe",
                "document joint", "annexe")
_NAV_MARKERS = ("advancedsearch", "javascript", "menu", "#", "signdocument")


class FetchError(RuntimeError):
    """Page de détail ou PDF indisponible."""


class DocumentTooLarge(RuntimeError):
    """PDF au-delà du plafond configuré."""


class NotAPdf(RuntimeError):
    """La réponse n'est pas un PDF."""


def _html_text(fragment: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub(" ", fragment)).strip()


def find_pdf_links(detail_url: str, html: str) -> list[str]:
    """Liens PDF candidats d'une page de détail, CPS/DCE en priorité."""
    preferred: list[str] = []
    others: list[str] = []
    seen: set[str] = set()
    for href, inner in _ANCHOR_RE.findall(html or ""):
        href = _html.unescape(href.strip())
        if not href or href.lower().startswith(("javascript:", "#", "mailto:")):
            continue
        low = href.lower()
        if any(marker in low for marker in _NAV_MARKERS):
            continue
        # Exclure les formulaires (données personnelles, loi 09-08) et les
        # téléchargements indirects (règlement, DCE) qui renvoient du HTML.
        if "demandetelechargement" in low or "downloadreglement" in low:
            continue
        # Seuls les liens directs vers un fichier sont conservés :
        #   - Avis complémentaire avec un idAvis numérique (PDF anonyme)
        #   - tout lien dont l'URL se termine par .pdf
        is_direct = (".pdf" in low) or ("downloadavisjal" in low and bool(re.search(r"idavis=\d+", low)))
        if not is_direct:
            continue
        absolute = urljoin(detail_url, href)
        if absolute in seen:
            continue
        seen.add(absolute)
        preferred.append(absolute)
    return preferred + others


MONTHS_FR = {
    "janv": 1, "fevr": 2, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
    "juil": 7, "aout": 8, "août": 8, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    "déc": 12,
}


def parse_publication_date(html: str) -> str | None:
    """Date de mise en ligne d'un avis (portail national), format ISO ou None."""
    m = re.search(r"mise en ligne\s*:\s*</div>\s*<div[^>]*>\s*<span[^>]*>\s*"
                  r"([A-Za-zÀ-ÿ]{2,4})\s+(\d{1,2})\s+([A-Za-zÀ-ÿ]{3,5})\.?\s+(\d{4})",
                  html, re.IGNORECASE)
    if not m:
        return None
    month_key = (m.group(3).lower()[:4])
    # unaccent
    import unicodedata
    month_key = unicodedata.normalize("NFKD", month_key).encode("ascii", "ignore").decode()
    month = MONTHS_FR.get(month_key)
    if not month:
        return None
    try:
        return date(int(m.group(4)), month, int(m.group(2))).isoformat()
    except ValueError:
        return None


def fetch_detail(url: str, *, session: Any = None,
                 timeout: float | None = None) -> str:
    """Récupère la page HTML de l'avis (session factice acceptée en test)."""
    client = session or requests
    try:
        resp = client.get(url, headers={"User-Agent": config.USER_AGENT},
                          timeout=timeout or config.REQUEST_TIMEOUT_S)
        resp.raise_for_status()
        return resp.text
    except requests.RequestException as exc:
        raise FetchError(f"detail {url[:120]} : {exc}") from exc


def download_pdf(url: str, *, max_bytes: int | None = None,
                 session: Any = None, timeout: float | None = None) -> bytes:
    """Télécharge un PDF avec garde-fou de taille et vérification du magic bytes."""
    limit = max_bytes or config.MAX_PDF_BYTES
    client = session or requests
    try:
        resp = client.get(url, headers={"User-Agent": config.USER_AGENT},
                          stream=True, timeout=timeout or config.REQUEST_TIMEOUT_S)
        resp.raise_for_status()
        chunks: list[bytes] = []
        size = 0
        for chunk in resp.iter_content(64 * 1024):
            if not chunk:
                continue
            size += len(chunk)
            if size > limit:
                resp.close()
                raise DocumentTooLarge(f"{size} octets > {limit}")
            chunks.append(chunk)
        data = b"".join(chunks)
        resp.close()
    except DocumentTooLarge:
        raise
    except requests.RequestException as exc:
        raise FetchError(f"pdf {url[:120]} : {exc}") from exc
    if not data.startswith(b"%PDF"):
        raise NotAPdf(f"contenu non PDF ({len(data)} octets)")
    return data
