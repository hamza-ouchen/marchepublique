"""Ingestion de textes fournis et validés : jamais de contenu juridique inventé."""

import hashlib
import json
import re
import time
from pathlib import Path
from uuid import uuid4

from .documents import extract_pdf
from .store import BackendError
from .token_budget import fit_budget, token_count

REG_APP = "sou9na_reglementation_rag"
REG_VERSION = "reg-e5-v1"


def prepare_regulatory(manifest_path):
    """Un manifeste décrit exactement les fichiers revus, leurs droits et empreintes."""
    path = Path(manifest_path).resolve()
    entries = json.loads(path.read_text(encoding="utf-8-sig"))["documents"]
    if not entries:
        raise BackendError("REGULATORY_SOURCES_REQUIRED")
    seen = set()
    result = []
    for entry in entries:
        source_id = entry["source_id"]
        if not re.fullmatch(r"[a-z0-9_-]{1,80}", source_id) or source_id in seen:
            raise BackendError("INVALID_REGULATORY_SOURCE_ID")
        seen.add(source_id)
        if (
            entry.get("validation") != "approved"
            or not entry.get("reviewed_by")
            or not entry.get("rights")
            or not entry.get("source")
            or not entry.get("source_url")
        ):
            raise BackendError("REGULATORY_SOURCE_NOT_APPROVED")
        file = (path.parent / entry["file"]).resolve()
        if not file.is_relative_to(path.parent) or file.suffix.lower() not in (
            ".pdf",
            ".txt",
            ".md",
        ):
            raise BackendError("INVALID_REGULATORY_PATH")
        digest = hashlib.sha256(file.read_bytes()).hexdigest()
        if digest != entry.get("sha256"):
            raise BackendError("REGULATORY_CHECKSUM_MISMATCH")
        if file.suffix.lower() == ".pdf":
            pages = extract_pdf(str(file))["pages"]
        else:
            pages = [file.read_text(encoding="utf-8-sig")]
        chunks = []
        for page, text in enumerate(pages, 1):
            if not text.strip():
                raise BackendError("REGULATORY_EMPTY_PAGE")
            # Le localisateur est un fragment, jamais un faux numéro d'article légal.
            for seq, part in enumerate(fit_budget(text.strip())):
                index = len(chunks)
                chunks.append(
                    {
                        "_id": f"reg:{source_id}:{digest}:{index}",
                        "rag_app": REG_APP,
                        "pipeline_version": REG_VERSION,
                        "kind": "chunk",
                        "type": "reglementation",
                        "source_id": source_id,
                        "document_sha256": digest,
                        "source": entry["source"],
                        "source_url": entry["source_url"],
                        "legal_validation": "approved_by_team",
                        "reviewed_by": entry["reviewed_by"],
                        "article": f"page {page}, fragment {seq + 1}"
                        if file.suffix == ".pdf"
                        else f"fragment {index + 1}",
                        "page": page if file.suffix == ".pdf" else None,
                        "chunk_index": index,
                        "text": part,
                        "text_sha256": hashlib.sha256(part.encode()).hexdigest(),
                    }
                )
        manifest = {
            "_id": f"reg:{source_id}:{digest}:manifest",
            "kind": "manifest",
            "rag_app": REG_APP,
            "pipeline_version": REG_VERSION,
            "type": "reglementation",
            "status": "ready",
            "source_id": source_id,
            "document_sha256": digest,
            "source": entry["source"],
            "chunk_count": len(chunks),
            "reviewed_by": entry["reviewed_by"],
            "source_url": entry["source_url"],
        }
        result.append((manifest, chunks))
    return result


def ingest_regulatory(manifest_path, store, repository):
    """Vérifie tous les fichiers avant le premier appel à Astra."""
    prepared = prepare_regulatory(manifest_path)
    store.inspect()
    reports = []
    for manifest, chunks in prepared:
        start = time.monotonic()
        run_id = f"rag:reg:{manifest['source_id']}:{uuid4()}"
        tokens = sum(token_count(c["text"]) for c in chunks)
        try:
            inserted = sum(store.put_immutable(chunk) for chunk in chunks)
            store.verify_chunks(chunks)
            store.put_immutable(manifest)
        except BackendError:
            repository.record_regulatory_run(run_id, "failed", tokens)
            raise
        repository.record_regulatory_run(run_id, "ready", tokens)
        reports.append(
            {
                "source": manifest["source"],
                "nb_chunks": len(chunks),
                "inserted": inserted,
                "skipped": len(chunks) - inserted,
                "vector_dim": 1024,
                "status": "ready",
                "run_id": run_id,
                "duration_seconds": round(time.monotonic() - start, 3),
            }
        )
    return {"status": "ready", "documents": reports}
