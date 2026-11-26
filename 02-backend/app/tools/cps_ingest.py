from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Callable

from app import db

_INSPECTEUR = Path(__file__).resolve().parents[3] / "04-langgraph" / "inspecteur"


def ingest_cps(reference: str, pdf_bytes: bytes, *,
               source_url: str | None = None,
               doc_type: str = "CPS",
               filename: str | None = None,
               storage_path: str | None = None,
               storage_uploader: Callable[[str, bytes], str] | None = None,
               request_id: str | None = None,
               idempotent: bool = True) -> dict[str, Any]:
    """Ingest an attachment with the Inspecteur document versioning pipeline."""
    if idempotent:
        existing = db.tender_document_by_reference(reference)
        if existing and existing.get("statut") in ("extracted", "ready"):
            return {
                "status": "skipped",
                "reason": "already_ingested",
                "document_id": existing["id"],
                "sections": existing.get("sections") or 0,
                "char_count": existing.get("char_count") or 0,
            }

    if str(_INSPECTEUR) not in sys.path:
        sys.path.insert(0, str(_INSPECTEUR))
    from cps_ingest import ingest_cps as ingest_document

    return ingest_document(
        reference,
        pdf_bytes,
        source_url=source_url,
        doc_type=doc_type,
        filename=filename,
        storage_path=storage_path,
        storage_uploader=storage_uploader,
        request_id=request_id,
    )
