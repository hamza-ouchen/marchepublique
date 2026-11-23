# =====================================================================
# Téléchargement du DOSSIER DE CONSULTATION (DCE) via le flux officiel
# du portail : page de détail -> formulaire de demande (identité
# déclarée) -> postback completeDownload -> ZIP -> PDFs.
#
# Capacité absente du module cps_download (qui ne traite que les PDF
# directs et exclut volontairement le lien DemandTelechargementDce).
# =====================================================================
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from pathlib import PurePosixPath
from typing import Any
from urllib.parse import urlencode

import requests

from . import config

_DCE_LINK_RE = re.compile(r'href="([^"]*EntrepriseDemandeTelechargementDce[^"]*)"')
_VALIDATE_BTN = "ctl0$CONTENU_PAGE$validateButton"
_COMPLETE_BTN = "ctl0$CONTENU_PAGE$EntrepriseDownloadDce$completeDownload"

_DOC_TYPE_RULES: list[tuple[str, re.Pattern[str]]] = [
    ("ADDITIF", re.compile(r"additif|rectificatif|avenant", re.I)),
    ("CPS", re.compile(r"\bc\.?p\.?s\b|cahier\s+des\s+(prescriptions|charges)", re.I)),
    ("AVIS", re.compile(r"\bavis\b", re.I)),
    ("DCE", re.compile(r"\brc\b|reglement|règlement", re.I)),
]
_DOC_PRIORITY = {"CPS": 0, "DCE": 1, "ADDITIF": 2, "AVIS": 3}


class DceError(RuntimeError):
    """Le portail n'a pas livré le dossier (lien absent, formulaire
    refusé, téléchargement vide)."""


def parse_portal_keys(source_url: str) -> tuple[str, str] | None:
    """(refConsultation, orgAcronyme) depuis la source_url stockée."""
    if not source_url or "refConsultation" not in source_url:
        return None
    m = re.search(r"refConsultation=(\d+)", source_url)
    org = re.search(r"orgAcronyme=([^&]+)", source_url)
    if not m or not org:
        return None
    return m.group(1), org.group(1)


def detail_url(refc: str, org: str) -> str:
    return (f"{config.PORTAL_BASE}/index.php?page=entreprise."
            f"EntrepriseDetailsConsultation&refConsultation={refc}"
            f"&orgAcronyme={org}&code=&retraits")


def classify_doc_type(filename: str) -> str:
    name = PurePosixPath(filename).stem
    for doc_type, rx in _DOC_TYPE_RULES:
        if rx.search(name):
            return doc_type
    return "DCE"


def sanitize_path_part(name: str, max_len: int = 120) -> str:
    """Nom sûr pour Supabase Storage (ASCII, 1 niveau). Les accents sont
    translittérés : le Storage rejette certains chemins non-ASCII."""
    import unicodedata
    cleaned = unicodedata.normalize("NFKD", name)
    cleaned = "".join(c for c in cleaned if not unicodedata.combining(c))
    cleaned = re.sub(r"\s+", "_", cleaned.strip())
    cleaned = re.sub(r"[^\w.\-]+", "", cleaned, flags=re.ASCII)
    return cleaned[:max_len] or "document.pdf"


def pdfs_from_zip(zip_bytes: bytes, _depth: int = 0,
                  _seen_sha: set[str] | None = None) -> list[tuple[str, bytes]]:
    """PDFs du ZIP du DCE, triés CPS d'abord. Récursif (profondeur 2) :
    certains acheteurs livrent le DCE en ZIP imbriqué. Dédoublonnés par
    sha256 ; les non-PDF (docx/xlsx) sont ignorés."""
    seen_sha = _seen_sha if _seen_sha is not None else set()
    out: list[tuple[str, bytes]] = []
    try:
        zf = zipfile.ZipFile(io.BytesIO(zip_bytes))
    except zipfile.BadZipFile:
        return out
    for info in zf.infolist():
        if info.is_dir():
            continue
        name = PurePosixPath(info.filename).name
        if (name.lower().endswith(".zip") and _depth < 2
                and 0 < info.file_size <= config.MAX_ZIP_BYTES):
            out.extend(pdfs_from_zip(zf.read(info), _depth + 1, seen_sha))
            continue
        if not name.lower().endswith(".pdf"):
            continue
        if info.file_size < 1024:
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


def fetch_dce_zip(session: requests.Session, dce_page_url: str) -> bytes:
    """Flux complet : page DCE -> formulaire -> postback -> ZIP.

    Lève DceError si le portail ne livre pas le dossier.
    """
    r = session.get(dce_page_url, timeout=config.REQUEST_TIMEOUT_S)
    if r.status_code != 200:
        raise DceError(f"page dce http {r.status_code}")
    fields = _parse_form(r.text)
    if not fields:
        raise DceError("formulaire introuvable sur la page DCE")
    for key, value in config.DCE_FORM.items():
        fields[f"ctl0$CONTENU_PAGE$EntrepriseFormulaireDemande${key}"] = value
    fields["ctl0$CONTENU_PAGE$EntrepriseFormulaireDemande$accepterConditions"] = "on"
    fields[_VALIDATE_BTN] = "Valider"
    fields["PRADO_POSTBACK_TARGET"] = _VALIDATE_BTN
    r2 = session.post(dce_page_url, data=fields, timeout=config.REQUEST_TIMEOUT_S)
    if r2.status_code != 200 or _COMPLETE_BTN.split("$")[-1] not in r2.text:
        raise DceError("formulaire DCE refusé (completeDownload absent)")
    f2 = _parse_form(r2.text)
    f2["PRADO_POSTBACK_TARGET"] = _COMPLETE_BTN
    r3 = session.post(dce_page_url, data=f2, timeout=180)
    if r3.status_code != 200 or not r3.content:
        raise DceError("téléchargement DCE vide")
    ctype = (r3.headers.get("Content-Type") or "").lower()
    if "zip" in ctype or r3.content[:4] == b"PK\x03\x04":
        return r3.content
    raise DceError("réponse non ZIP après completeDownload")


def _parse_form(html: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for m in re.finditer(r"<input\b[^>]*>", html):
        tag = m.group(0)
        name_m = re.search(r'name="([^"]+)"', tag)
        if not name_m:
            continue
        type_m = re.search(r'type="([^"]+)"', tag)
        if (type_m.group(1).lower() if type_m else "text") not in \
                {"hidden", "text", "submit"}:
            continue
        value_m = re.search(r'value="([^"]*)"', tag)
        fields[name_m.group(1)] = value_m.group(1) if value_m else ""
    return fields


def cps_relay_url(refc: str, org: str) -> str:
    """URL publique de la page CPS (traçabilité de la source)."""
    return f"{config.AO_BASE}/cps?{urlencode({'ref': refc, 'org': org})}"
