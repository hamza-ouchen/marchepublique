# =====================================================================
# Ingestion CPS : idempotence + extraction + écriture DB.
# Pas de LLM, pas d'appel Astra (Ouchen s'en charge après 'extracted').
# Stockage Supabase Storage : optionnel via `storage_uploader` callable.
# =====================================================================
from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from soukna_graph import db
from soukna_graph.tools import cps_extract

MAX_PDF_BYTES = 25 * 1024 * 1024   # 25 Mo
MAX_PAGES = 200


def ingest_cps(reference: str, pdf_bytes: bytes, *,
               source_url: str | None = None,
               doc_type: str = "CPS",
               filename: str | None = None,
               storage_path: str | None = None,
               storage_uploader: Callable[[str, bytes], str] | None = None,
               request_id: str | None = None,
               idempotent: bool = True) -> dict[str, Any]:
    """Ingère un CPS (PDF) pour un tender.

    Retourne un dict {status, document_id, sections, char_count, ...}.
    Idempotent : si un document 'extracted'/'ready' existe déjà pour ce
    reference, on ne ré-ingère pas. `idempotent=False` permet d'ingérer
    plusieurs pièces d'un même dossier DCE (le dédoublonnage exact reste
    assuré par l'UNIQUE sha256 en base).
    """
    # 1) Idempotence
    existing = db.tender_document_by_reference(reference) if idempotent else None
    if existing and existing.get("statut") in ("extracted", "ready"):
        return {"status": "skipped", "reason": "already_ingested",
                "document_id": existing["id"],
                "sections": existing.get("sections") or 0,
                "char_count": existing.get("char_count") or 0}

    # 2) Garde-fous taille
    if len(pdf_bytes) > MAX_PDF_BYTES:
        return {"status": "skipped", "reason": "too_large",
                "size_bytes": len(pdf_bytes)}

    # 3) Extraction
    info = cps_extract.extract_text(pdf_bytes)
    if info["pages"] and info["pages"] > MAX_PAGES:
        return {"status": "skipped", "reason": "too_many_pages",
                "pages": info["pages"]}

    # 4) Stockage (optionnel)
    if storage_path is None:
        storage_path = f"{reference}/{(filename or 'cps.pdf')}"
    if storage_uploader is not None:
        try:
            storage_path = storage_uploader(storage_path, pdf_bytes)
        except Exception as exc:
            return {"status": "echec", "reason": "storage_upload_failed",
                    "error": str(exc)[:200]}

    # 5) Découpage en sections
    sections = cps_extract.split_into_sections(info["text"])

    # 6) Statut final — ingestion TOTALE : même un PDF scanné sans couche
    # texte est stocké ; la faible qualité de texte est tracée dans
    # echec_raison (sans bloquer) ; seuls les PDF illisibles (pages=0)
    # restent en echec.
    has_text = len(info["text"].strip()) >= cps_extract.MIN_TEXT_CHARS
    if info["pages"] and info["pages"] > 0:
        statut = "extracted"
        echec_raison = (None if has_text
                        else f"texte insuffisant ({info['char_count']} chars)")
    else:
        statut = "echec"
        echec_raison = "pdf illisible (aucune page)"

    # 7) Écriture DB
    doc = db.tender_document_create(
        reference=reference,
        storage_path=storage_path,
        sha256=info["sha256"],
        doc_type=doc_type,
        filename=filename,
        mime="application/pdf",
        size_bytes=len(pdf_bytes),
        pages=info["pages"],
        extraction=info["extraction"],
        extracted_text=info["text"],
        source_url=source_url,
        request_id=request_id,
        statut=statut,
        echec_raison=echec_raison,
        sections=len(sections),
        char_count=info["char_count"],
        downloaded_at=datetime.now(timezone.utc),
    )
    if not doc:
        return {"status": "echec", "reason": "db_insert_failed"}

    if sections and statut == "extracted":
        db.cps_sections_replace(doc["id"], sections)

    # 8) Si echec (texte insuffisant), statut reste echec avec raison
    return {
        "status": statut,
        "document_id": doc["id"],
        "sections": len(sections),
        "char_count": info["char_count"],
        "pages": info["pages"],
        "extraction": info["extraction"],
        "sha256": info["sha256"],
    }