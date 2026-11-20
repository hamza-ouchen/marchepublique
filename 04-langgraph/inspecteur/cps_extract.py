# =====================================================================
# Extraction déterministe de texte CPS (PDF) -> sections.
# Pas de LLM. pypdf en premier ; OCR (pytesseract) si < 100 caractères.
# =====================================================================
from __future__ import annotations

import hashlib
import io
import re
from typing import Any

MIN_TEXT_CHARS = 100


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
    import pytesseract
    from pdf2image import convert_from_bytes
    images = convert_from_bytes(data, dpi=200)
    pages = []
    for i, img in enumerate(images):
        pages.append(f"----- PAGE {i+1} -----\n" + (pytesseract.image_to_string(img, lang="fra") or ""))
    return "\n\n".join(pages), len(images)


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
    if len(text.strip()) < MIN_TEXT_CHARS:
        # 2) OCR fallback
        try:
            ocr_text, ocr_pages = extract_with_ocr(data)
            if len(ocr_text.strip()) > len(text.strip()):
                text, pages = ocr_text, ocr_pages
                extraction = "ocr_tesseract_fra_best"
        except (ImportError, Exception):
            # OCR indisponible : on garde pypdf tel quel
            if pypdf_err:
                extraction = f"pypdf_error:{pypdf_err[:80]}"

    return {
        "text": text,
        "pages": pages,
        "extraction": extraction,
        "sha256": sha,
        "char_count": len(text.strip()),
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