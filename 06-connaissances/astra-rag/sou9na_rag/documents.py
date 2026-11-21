"""Extraction paginée et découpage respectant les questions et les sources."""

import hashlib
import re
import unicodedata
from bisect import bisect_right
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .token_budget import fit_budget

APP = "sou9na_reference_rag"
VERSION = "qa-pages-e5-v2"
CORPUS = "soukna_reference"
MAX_CHARS = 1800
OVERLAP = 180
QUESTION = re.compile(r"(?m)^\[Q-(\d{3})\]\s*")
SECTION = re.compile(r"(?m)^0[0-6]\.\s*[^\n]+\n?")
FOOTER = re.compile(r"(?m)^SOUKNA[^\n]*Page\s+\d+\s+(?:of|sur|/)\s*\d+\s*$")


class DocumentError(ValueError):
    """Document incompatible avec ce corpus de questions structurées."""


def clean_page(text: str) -> str:
    """Préserve les mots et l'arabe, retire seulement les artefacts simples."""
    text = unicodedata.normalize("NFC", text).replace("\x00", " ")
    text = FOOTER.sub("", text)
    text = re.sub(r"[ \t]+", " ", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def split_text(text: str, max_chars: int = MAX_CHARS) -> list[str]:
    """Découpe sans troncature silencieuse avec recouvrement aux frontières."""
    if max_chars <= OVERLAP + 20:
        raise ValueError("Taille de passage trop petite")
    text = text.strip()
    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            boundary = max(text.rfind("\n", start, end), text.rfind(" ", start, end))
            if boundary > start + max_chars // 2:
                end = boundary
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end == len(text):
            break
        next_start = max(start + 1, end - OVERLAP)
        boundary = text.find(" ", next_start, end)
        start = boundary + 1 if boundary >= 0 else next_start
    return pieces


def extract_pdf(path: str) -> dict[str, Any]:
    """Lit toutes les pages du PDF, sans OCR ou limite de texte implicite."""
    file = Path(path)
    if not file.is_file() or file.suffix.lower() != ".pdf":
        raise DocumentError("Un fichier PDF existant est requis")
    try:
        reader = PdfReader(file)
    except PdfReadError:
        raise DocumentError("PDF invalide ou tronque") from None
    if reader.is_encrypted:
        raise DocumentError("PDF chiffre non pris en charge")
    pages = [clean_page(page.extract_text() or "") for page in reader.pages]
    if not pages or any(len(page.strip()) < 20 for page in pages):
        raise DocumentError("Page vide ou non extractible : OCR/verification humaine requis")
    return {
        "document_sha256": hashlib.sha256(file.read_bytes()).hexdigest(),
        "document": file.name,
        "pages": pages,
        "page_count": len(pages),
    }


def make_chunks(extracted: dict[str, Any], expected_questions: int = 125) -> list[dict]:
    """Conserve les blocs Q/R, les tableaux de synthèse et toutes les pages du glossaire."""
    pages = extracted["pages"]
    offsets: list[int] = []
    position = 0
    for page in pages:
        offsets.append(position)
        position += len(page) + 2
    text = "\n\n".join(pages)
    matches = list(QUESTION.finditer(text))
    ids = [int(match[1]) for match in matches]
    if ids != list(range(1, expected_questions + 1)):
        raise DocumentError("Questions absentes, dupliquees ou desordonnees")
    glossary = re.search(r"(?m)^06\.\s*Glossaire", text)
    if not glossary or glossary.start() <= matches[-1].start():
        raise DocumentError("Glossaire final introuvable")
    chunks: list[dict] = []

    def append_block(block: str, block_id: str, kind: str, start: int, end: int) -> None:
        content = SECTION.sub("", block).strip()
        category_match = re.search(r"Catégorie\s*:\s*(.*?)\s*·", content, re.S)
        source_match = re.search(r"\bSource\s*:\s*(.*)", content, re.S)
        category = re.sub(r"\s+", " ", category_match[1]) if category_match else kind
        declared_source = (
            re.sub(r"\s+", " ", source_match[1]).strip() if source_match else "PDF fourni"
        )
        prefix = content.splitlines()[0] if kind == "qa" else ""
        parts = [
            bounded
            for part in split_text(content, MAX_CHARS - len(prefix) - 2)
            for bounded in fit_budget(part, prefix)
        ]
        page_start = bisect_right(offsets, start)
        page_end = bisect_right(offsets, max(start, end - 1))
        digest = extracted["document_sha256"]
        for index, part in enumerate(parts):
            chunk_text = part
            chunk_id = f"s9rag:{VERSION}:{digest}:{block_id}:{index:03d}"
            chunks.append(
                {
                    "_id": chunk_id,
                    "rag_app": APP,
                    "kind": "chunk",
                    "corpus": CORPUS,
                    "pipeline_version": VERSION,
                    "document_sha256": digest,
                    "document": extracted["document"],
                    "block_id": block_id,
                    "chunk_index": index,
                    "content_type": kind,
                    "category": category,
                    "declared_source": declared_source,
                    "page_start": page_start,
                    "page_end": page_end,
                    "source_kind": "provided_reference_pdf",
                    "legal_validation": "not_verified",
                    "text": chunk_text,
                    "text_sha256": hashlib.sha256(chunk_text.encode()).hexdigest(),
                }
            )

    # Un bloc par page avant les Q/R : les tableaux ne sont pas perdus.
    first_question = matches[0].start()
    for i, page in enumerate(pages):
        start = offsets[i]
        if start >= first_question:
            break
        end = min(start + len(page), first_question)
        if text[start:end].strip():
            append_block(text[start:end], f"SUMMARY-{i + 1:03}", "summary", start, end)
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else glossary.start()
        block = text[match.start() : end].rstrip()
        append_block(block, f"Q-{match[1]}", "qa", match.start(), match.start() + len(block))
    for i, page in enumerate(pages):
        start = max(offsets[i], glossary.start())
        end = offsets[i] + len(page)
        if end > glossary.start():
            append_block(text[start:end], f"GLOSSARY-{i + 1:03}", "glossary", start, end)
    if not chunks or any(not c["text"].strip() for c in chunks):
        raise DocumentError("Un passage vide a ete produit")
    return chunks
