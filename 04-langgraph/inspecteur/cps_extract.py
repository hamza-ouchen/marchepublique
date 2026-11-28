# =====================================================================
# Extraction déterministe de texte CPS (PDF) -> sections.
# Pas de LLM. pypdf en premier ; OCR (pytesseract) si < 100 caractères.
# =====================================================================
from __future__ import annotations

import hashlib
import os
import io
import re
import tempfile
from pathlib import Path
from typing import Any

MIN_TEXT_CHARS = 100

# Tesseract data local : évite d'écrire dans "Program Files" sur Windows.
if not os.environ.get("TESSDATA_PREFIX"):
    _local_tessdata = Path(tempfile.gettempdir()) / "opencode" / "tessdata"
    if (_local_tessdata / "fra.traineddata").exists():
        os.environ["TESSDATA_PREFIX"] = str(_local_tessdata)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_with_pypdf(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader
    reader = PdfReader(io.BytesIO(data))
    pages = []
    for p in reader.pages:
        pages.append(p.extract_text() or "")
    text = "\n\n".join(f"----- PAGE {i+1} -----\n{t}" for i, t in enumerate(pages))
    return text, len(reader.pages)


def extract_with_ocr(data: bytes) -> tuple[str, int]:
    # Fallback OCR pour pages scannées. Requiert pytesseract + pdf2image +
    # binaire tesseract installé. Lève ImportError si absent.
    import pymupdf
    import pytesseract
    tesseract_cmd = os.environ.get("TESSERACT_CMD",
                                    r"C:\Program Files\Tesseract-OCR\tesseract.exe")
    if os.path.exists(tesseract_cmd):
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
    # PyMuPDF est déjà requis par requirements.txt : on évite une dépendance
    # Poppler/pdf2image supplémentaire (souvent absente en environnement local).
    dpi = int(os.environ.get("SOU9NA_OCR_DPI", "150"))
    pages = []
    with tempfile.TemporaryDirectory(prefix="sou9na-ocr-") as folder:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            for index, page in enumerate(doc, 1):
                pix = page.get_pixmap(dpi=dpi)
                image_path = os.path.join(folder, f"page-{index}.png")
                pix.save(image_path)
                text = pytesseract.image_to_string(image_path, lang="fra", timeout=60)
                pages.append(f"----- PAGE {index} -----\n" + (text or ""))
    return "\n\n".join(pages), len(pages)


def text_length(text: str) -> int:
    return len(re.sub(r"(?m)^----- PAGE \d+ -----\s*", "", text).strip())


def _money(raw: str | None) -> int | None:
    if not raw:
        return None
    cleaned = re.sub(r"[^\d\s,\.]", "", str(raw))
    cleaned = cleaned.replace("\u00a0", " ").strip().replace(" ", "")
    if "," in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    else:
        cleaned = cleaned.replace(",", "")
    try:
        value = float(cleaned)
    except (ValueError, TypeError):
        return None
    return int(round(value)) if value >= 1000 else None


def _first_amount(text: str, labels: tuple[str, ...]) -> int | None:
    for label in labels:
        pattern = (
            rf"{label}(?:\s+(?:provisoire|d[ée]finitive|estimatif|pr[ée]visionnel))?"
            rf"(?:\s*\([^)]{{0,40}}\))?"
            rf"\s*(?:de|d['’]|gonfl[ée]e?|fix[ée]e?|:|=)?\s*"
            r"(\d{1,3}(?:[\s\u00a0]\d{3})+|\d{4,})"
        )
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            amount = _money(match.group(1))
            if amount:
                return amount
    return None


def _snippet(text: str, pattern: str, width: int = 180) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - 40)
    return re.sub(r"\s+", " ", text[start:match.end() + width]).strip()


_MONTHS_FR = {
    "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4,
    "mai": 5, "juin": 6, "juillet": 7, "août": 8, "aout": 8,
    "septembre": 9, "octobre": 10, "novembre": 11, "décembre": 12,
    "decembre": 12,
}
_DATE_RE = re.compile(
    r"(?P<day>\d{1,2})(?:\s*[/\-]\s*|\s+)(?P<month>\d{1,2}|"
    + "|".join(_MONTHS_FR) + r")(?:\s*[/\-]\s*|\s+)(?P<year>\d{4})",
    re.IGNORECASE,
)


def _iso_date(value: str) -> str | None:
    from datetime import date

    match = _DATE_RE.search(value or "")
    if not match:
        return None
    month = match.group("month").lower()
    if month.isdigit():
        number = int(month)
    else:
        number = _MONTHS_FR.get(month)
    if not number or not 1 <= number <= 12:
        return None
    day, year = int(match.group("day")), int(match.group("year"))
    if not 1 <= day <= 31 or not 1900 <= year <= 2100:
        return None
    try:
        return date(year, number, day).isoformat()
    except ValueError:
        return None


def _find_date(text: str, pattern: str) -> tuple[str | None, str | None]:
    from tender_times import clock_after_date

    match = re.search(pattern, text, re.IGNORECASE)
    if match and (day := _DATE_RE.search(match.group(0))):
        value = _iso_date(day.group())
        if value:
            return value, clock_after_date(match.group(0)[day.end():])
    return None, None


def _extract_lots(text: str, title: str = "") -> list[str]:
    source = f"{title or ''} {text or ''}"
    found: list[str] = []
    if re.search(r"\blot\s+unique\b", source, re.IGNORECASE):
        found.append("Lot unique")
    for match in re.finditer(r"\blots?\s*(?:n[°o]\s*)?(\d{1,2})\b", source, re.IGNORECASE):
        label = f"Lot {int(match.group(1))}"
        if label not in found:
            found.append(label)
    for match in re.finditer(r"\b(\d{1,2})\s*lots?\b", source, re.IGNORECASE):
        count = int(match.group(1))
        if 1 <= count <= 20:
            for number in range(1, count + 1):
                label = f"Lot {number}"
                if label not in found:
                    found.append(label)
    return found[:20]


def _extract_qualifications(text: str) -> list[str]:
    pattern = (
        r"[^.]{0,140}(?:qualification|classement|cat[ée]gorie|"
        r"r[ée]f[ée]rence professionnelle|attestation|certificat|"
        r"agr[ée]ment|habilitation)[^.]{0,180}\."
    )
    found: list[str] = []
    for match in re.finditer(pattern, text or "", re.IGNORECASE):
        snippet = re.sub(r"\s+", " ", match.group(0)).strip()
        if 20 <= len(snippet) <= 320 and snippet not in found:
            found.append(snippet)
        if len(found) >= 5:
            break
    return found


def extract_detail(text: str, title: str = "") -> dict[str, Any]:
    """Signaux documentaires explicites — aucune valeur n'est inventée."""
    clean = re.sub(r"\s+", " ", text or "").strip()
    caution = _first_amount(clean, ("caution", "garantie"))
    budget = _first_amount(clean, ("montant estimatif", "montant pr[ée]visionnel",
                                   "montant", "budget", "enveloppe"))
    penalty = _snippet(clean, r"p[ée]nalit[ée]s?|p[ée]nalit[ée] de retard")
    qualification = _snippet(clean, r"qualification|classement|cat[ée]gorie")
    delai_match = re.search(r"d[ée]lai[^.]{0,120}?(\d{1,4})\s*jours", clean, re.IGNORECASE)
    delai_jours = int(delai_match.group(1)) if delai_match else None
    visit = _snippet(clean, r"visite (?:obligatoire|sur place)|reconnaissance des lieux")
    documents = _snippet(clean, r"pi[èe]ces (?:administratives|techniques)|dossier administratif")
    lots = _extract_lots(clean, title)
    qualifications = _extract_qualifications(clean)
    date_publication, heure_publication = _find_date(
        clean, r"(?:date de )?(?:publication|mise en ligne|diffusion)[^.]{0,80}"
    )
    date_remise, heure_remise = _find_date(
        clean,
        r"(?:date(?: et heure)?(?: de)? limite(?: de)? (?:remise|r[ée]ception|cl[ôo]ture)|"
        r"remise des offres|cl[ôo]ture des offres)[^.]{0,80}",
    )

    signals = [key for key, value in (
        ("caution", caution), ("budget", budget), ("delai", delai_jours), ("penalites", penalty),
        ("qualification", qualification or qualifications), ("visite", visit),
        ("documents", documents), ("lots", lots), ("dates", date_publication or date_remise),
    ) if value]

    return {
        "title": title[:250],
        "caution_mad": caution,
        "budget_mad": budget,
        "delai_jours": delai_jours,
        "date_publication": date_publication,
        "date_remise": date_remise,
        "heure_publication": heure_publication,
        "heure_remise": heure_remise,
        "lots": lots,
        "qualifications_exigees": qualifications,
        "penalties": bool(penalty),
        "penalty_text": penalty[:300],
        "qualification": qualification[:300],
        "visit": visit[:300],
        "documents": documents[:300],
        "text_length": len(clean),
        "signals": signals,
        "deep_candidate": bool(caution or budget or penalty),
        "quality": "riche" if (caution and budget) else ("partiel" if signals else "pauvre"),
    }


def extract_text(data: bytes) -> dict[str, Any]:
    """Retourne {text, pages, extraction, sha256, char_count}.

    Stratégie : pypdf d'abord ; si le texte extrait fait moins de
    MIN_TEXT_CHARS, on tente l'OCR. Si l'OCR est indisponible, on garde
    le résultat pypdf (même vide) et on le signale.
    """
    sha = _sha256(data)
    # 1) pypdf
    try:
        text, pages = extract_with_pypdf(data)
    except Exception as exc:
        text, pages = "", 0
        pypdf_err = str(exc)
    else:
        pypdf_err = None

    extraction = "pypdf"
    if text_length(text) < MIN_TEXT_CHARS and os.environ.get("SOU9NA_OCR", "1").lower() not in ("0", "false", "non", "no"):
        # 2) OCR fallback
        try:
            ocr_text, ocr_pages = extract_with_ocr(data)
            if text_length(ocr_text) > text_length(text):
                text, pages = ocr_text, ocr_pages
                extraction = "ocr_tesseract_fra_best"
        except (ImportError, Exception) as exc:  # noqa: BLE001
            # OCR indisponible ou échec mémoire : on garde pypdf tel quel.
            # On ne remplace PAS le libellé pypdf par une erreur OCR : les
            # appelants doivent pouvoir distinguer une extraction pypdf
            # valide d'une erreur de lecture du PDF lui-même.
            if pypdf_err:
                extraction = f"pypdf_error:{pypdf_err[:80]}"

    return {
        "text": text,
        "pages": pages,
        "extraction": extraction,
        "sha256": sha,
        "char_count": text_length(text),
    }


# ------------------------------------------------------------------ #
# Découpage en sections par titres numérotés (regex déterministe).
# ------------------------------------------------------------------ #
_HEADER_RE = re.compile(
    r"^(?P<head>"
    r"Article\s+\d+(?:\.\d+)*\.?"          # Article 1. / Article 1.2
    r"|Art(?:icle)?\s*[IVXLC]+\."          # Article IV.
    r"|\d+(?:\.\d+)*\s*[-–.]\s*\S"        # 1. Titre / 1- Titre
    r"|Chapitre\s+[IVXLC\d]+"              # Chapitre I / 1
    r"|Titre\s+[IVXLC\d]+"
    r"|Pi[eè]ce\s+[IVXLC\d]+"             # Pièce III
    r"|Section\s+\d+"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


def split_into_sections(text: str) -> list[dict[str, Any]]:
    """Découpe le texte en sections selon les titres numérotés.

    Retourne une liste de dicts :
      {section_no, numero, titre, texte, pages_section}
    Si aucun titre n'est détecté, retourne une section unique (section_no=1).
    """
    if not text.strip():
        return []

    # Trouver toutes les positions de début de section.
    matches = list(_HEADER_RE.finditer(text))
    if not matches:
        return [{"section_no": 1, "numero": None, "titre": None,
                 "texte": text.strip(), "pages_section": _pages_for(text)}]

    sections: list[dict[str, Any]] = []
    # Texte avant le premier titre = préambule (section 0 -> on le garde en 1 si non vide)
    preamble = text[:matches[0].start()].strip()
    # Retirer les marqueurs de page du préambule (bruit)
    preamble = re.sub(r"----- PAGE \d+ -----\n?", "", preamble).strip()
    if preamble and len(preamble) > 20:
        page_no = None
        for pm in re.finditer(r"----- PAGE (\d+) -----", text[:matches[0].start()]):
            page_no = int(pm.group(1))
        sections.append({"section_no": len(sections) + 1, "numero": None,
                         "titre": "Préambule", "texte": preamble,
                         "pages_section": (f"p. {page_no}" if page_no else None)})

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        if not chunk:
            continue
        # Première ligne = titre
        lines = chunk.splitlines()
        title_line = lines[0].strip() if lines else ""
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        if not body:
            body = chunk
            title_line = None
        # numero : partie numérique initiale du titre
        num_match = re.match(r"(\d+(?:\.\d+)*)", title_line or "")
        numero = num_match.group(1) if num_match else None
        # page(s) : dernier marqueur de page avant le début de la section
        page_no = None
        for pm in re.finditer(r"----- PAGE (\d+) -----", text[:start]):
            page_no = int(pm.group(1))
        sections.append({
            "section_no": len(sections) + 1,
            "numero": numero,
            "titre": title_line[:200] if title_line else None,
            "texte": (body if body else chunk)[:50000],
            "pages_section": (f"p. {page_no}" if page_no else None),
        })

    # Renumeroter proprement 1..N
    for idx, s in enumerate(sections, 1):
        s["section_no"] = idx
    return sections


def _pages_for(chunk: str) -> str | None:
    pages = sorted({int(m) for m in re.findall(r"----- PAGE (\d+) -----", chunk)})
    if not pages:
        return None
    if len(pages) == 1:
        return f"p. {pages[0]}"
    return f"p. {pages[0]}-{pages[-1]}"
