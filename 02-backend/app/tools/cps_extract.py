# =====================================================================
# Extraction déterministe de texte de documents PDF (CPS/DCE).
# pypdf d'abord, OCR (pytesseract) si texte insuffisant ; découpage en
# sections par titres numérotés. Aucun LLM.
# =====================================================================
from __future__ import annotations

import hashlib
import io
import re
from typing import Any

from .. import config

MIN_TEXT_CHARS = 100


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def extract_with_pypdf(data: bytes) -> tuple[str, int]:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(data))
    pages = [(p.extract_text() or "") for p in reader.pages]
    text = "\n\n".join(f"----- PAGE {i+1} -----\n{t}" for i, t in enumerate(pages))
    return text, len(reader.pages)


def _tesseract_cmd() -> str | None:
    """Binaire tesseract : config, PATH, puis emplacements Windows courants."""
    import os
    from shutil import which

    if config.TESSERACT_CMD:
        return config.TESSERACT_CMD
    found = which("tesseract")
    if found:
        return found
    for candidate in (
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    ):
        if os.path.exists(candidate):
            return candidate
    return None


def _ocr_lang() -> str:
    """Langue disponible dans tessdata (fra de préférence, repli eng)."""
    import os

    requested = config.OCR_LANG
    tessdata = config.TESSDATA_DIR
    if os.path.exists(os.path.join(tessdata, requested + ".traineddata")):
        return requested
    if os.path.exists(os.path.join(tessdata, "eng.traineddata")):
        return "eng"
    return requested


def extract_with_ocr(data: bytes) -> tuple[str, int]:
    """OCR des PDF scannés via PyMuPDF (rendu) + tesseract, sans poppler."""
    import os

    import pymupdf
    import pytesseract
    from PIL import Image

    cmd = _tesseract_cmd()
    if not cmd:
        raise RuntimeError("binaire tesseract introuvable (TESSERACT_CMD)")
    pytesseract.pytesseract.tesseract_cmd = cmd
    lang = _ocr_lang()
    tessdata = config.TESSDATA_DIR
    if os.path.isdir(tessdata):
        os.environ["TESSDATA_PREFIX"] = tessdata

    pages: list[str] = []
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        for index, page in enumerate(doc):
            pix = page.get_pixmap(dpi=config.OCR_DPI)
            image = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            text = pytesseract.image_to_string(image, lang=lang)
            pages.append(f"----- PAGE {index + 1} -----\n{text or ''}")
    return "\n\n".join(pages), len(pages)


def extract_text(data: bytes) -> dict[str, Any]:
    """Retourne {text, pages, extraction, sha256, char_count}."""
    sha = _sha256(data)
    pypdf_err = None
    try:
        text, pages = extract_with_pypdf(data)
    except Exception as exc:
        text, pages = "", 0
        pypdf_err = str(exc)

    extraction = "pypdf"
    if len(text.strip()) < MIN_TEXT_CHARS:
        try:
            ocr_text, ocr_pages = extract_with_ocr(data)
            if len(ocr_text.strip()) > len(text.strip()):
                text, pages = ocr_text, ocr_pages
                extraction = "ocr_tesseract_fra_best"
        except Exception:
            if pypdf_err:
                extraction = f"pypdf_error:{pypdf_err[:80]}"
    return {
        "text": text,
        "pages": pages,
        "extraction": extraction,
        "sha256": sha,
        "char_count": len(text.strip()),
    }


_HEADER_RE = re.compile(
    r"^(?P<head>"
    r"Article\s+\d+(?:\.\d+)*\.?"
    r"|Art(?:icle)?\s*[IVXLC]+\."
    r"|\d+(?:\.\d+)*\s*[-–.]\s*\S"
    r"|Chapitre\s+[IVXLC\d]+"
    r"|Titre\s+[IVXLC\d]+"
    r"|Pi[eè]ce\s+[IVXLC\d]+"
    r"|Section\s+\d+"
    r")",
    re.IGNORECASE | re.MULTILINE,
)


def split_into_sections(text: str) -> list[dict[str, Any]]:
    """Découpe le texte en sections selon les titres numérotés."""
    if not text.strip():
        return []
    matches = list(_HEADER_RE.finditer(text))
    if not matches:
        return [{"section_no": 1, "numero": None, "titre": None,
                 "texte": text.strip(), "pages_section": _pages_for(text)}]

    sections: list[dict[str, Any]] = []
    preamble = re.sub(r"----- PAGE \d+ -----\n?", "",
                      text[:matches[0].start()]).strip()
    if preamble and len(preamble) > 20:
        page_no = None
        for pm in re.finditer(r"----- PAGE (\d+) -----", text[:matches[0].start()]):
            page_no = int(pm.group(1))
        sections.append({"section_no": 1, "numero": None, "titre": "Préambule",
                         "texte": preamble,
                         "pages_section": (f"p. {page_no}" if page_no else None)})

    for i, m in enumerate(matches):
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        chunk = text[start:end].strip()
        if not chunk:
            continue
        lines = chunk.splitlines()
        title_line = lines[0].strip() if lines else ""
        body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
        if not body:
            body, title_line = chunk, None
        num_match = re.match(r"(\d+(?:\.\d+)*)", title_line or "")
        numero = num_match.group(1) if num_match else None
        page_no = None
        for pm in re.finditer(r"----- PAGE (\d+) -----", text[:start]):
            page_no = int(pm.group(1))
        sections.append({
            "section_no": 0,  # renuméroté ci-dessous
            "numero": numero,
            "titre": title_line[:200] if title_line else None,
            "texte": (body if body else chunk)[:50000],
            "pages_section": (f"p. {page_no}" if page_no else None),
        })
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
