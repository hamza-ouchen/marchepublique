# =====================================================================
# Ingestion CPS : idempotence + extraction + écriture DB.
# Pas de LLM, pas d'appel Astra (Ouchen s'en charge après 'extracted').
# Stockage Supabase Storage : optionnel via `storage_uploader` callable.
# =====================================================================
from __future__ import annotations

import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import db_cps as db
import cps_extract

MAX_PDF_BYTES = 25 * 1024 * 1024   # 25 Mo
MAX_PAGES = 200


def ingest_cps(reference: str, pdf_bytes: bytes, *,
               source_url: str | None = None,
               doc_type: str = "CPS",
               filename: str | None = None,
               storage_path: str | None = None,
               storage_uploader: Callable[[str, bytes], str] | None = None,
               request_id: str | None = None) -> dict[str, Any]:
    """Ingère un CPS (PDF) pour un tender.

    Retourne un dict {status, document_id, sections, char_count, ...}.
    Idempotent pour une même référence et un même contenu.
    """
    if len(pdf_bytes) > MAX_PDF_BYTES:
        return {"status": "skipped", "reason": "too_large",
                "size_bytes": len(pdf_bytes)}

    digest = hashlib.sha256(pdf_bytes).hexdigest()
    existing = db.tender_document_by_hash(reference, digest)
    if existing and existing["statut"] in ("extracted", "ready") and (
        storage_uploader is None or existing["storage_path"].startswith("versions/")
    ):
        return {"status": "skipped", "reason": "already_ingested",
                "document_id": existing["id"],
                "sections": existing.get("sections") or 0,
                "char_count": existing.get("char_count") or 0}

    # 3) Extraction
    info = cps_extract.extract_text(pdf_bytes)
    signaux = cps_extract.extract_detail(info["text"], filename or "")
    if info["pages"] and info["pages"] > MAX_PAGES:
        return {"status": "skipped", "reason": "too_many_pages",
                "pages": info["pages"]}

    # 4) Stockage (optionnel)
    if storage_path is None:
        storage_path = f"versions/{digest}.pdf" if storage_uploader else f"{reference}/{filename or 'cps.pdf'}"
    existing_upload = existing and existing["statut"] in ("stored", "echec") and (
        existing["storage_path"] == storage_path == f"versions/{digest}.pdf"
        and existing.get("storage_bucket", "cps-originaux") == "cps-originaux"
    )
    if storage_uploader is not None and not existing_upload:
        try:
            storage_path = storage_uploader(storage_path, pdf_bytes)
        except Exception as exc:
            return {"status": "echec", "reason": "storage_upload_failed",
                    "error": str(exc)[:200]}

    # 5) Découpage en sections
    sections = cps_extract.split_into_sections(info["text"])

    # 6) Statut final
    has_text = info["char_count"] >= cps_extract.MIN_TEXT_CHARS
    statut = "extracted" if has_text else "echec"
    echec_raison = None if has_text else "texte insuffisant (< 100 chars)"

    # 7) Écriture DB
    doc = db.save_document_version(
        sections if has_text else [],
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
        sections=len(sections) if has_text else 0,
        char_count=info["char_count"],
        downloaded_at=datetime.now(timezone.utc),
    )
    if not doc:
        return {"status": "echec", "reason": "db_insert_failed"}
    if statut == "echec" and doc["statut"] in ("extracted", "ready"):
        return {"status": "skipped", "reason": "already_ingested", "document_id": doc["id"]}

    # 8) Si echec (texte insuffisant), statut reste echec avec raison
    return {
        "status": statut,
        "document_id": doc["id"],
        "sections": len(sections),
        "char_count": info["char_count"],
        "pages": info["pages"],
        "extraction": info["extraction"],
        "sha256": info["sha256"],
        "signals": signaux,
    }
