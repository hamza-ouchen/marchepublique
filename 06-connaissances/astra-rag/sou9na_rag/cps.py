"""Ingestion CPS : instantané Supabase, écriture idempotente, publication vérifiée."""

import hashlib
import json
import re
import time
from uuid import uuid4

from .store import BackendError
from .token_budget import fit_budget, token_count

CPS_APP = "sou9na_cps_rag"
CPS_VERSION = "cps-e5-v1"


def fingerprint(document: dict, sections: list[dict]) -> str:
    """Détecte aussi un changement du texte extrait à PDF inchangé."""
    payload = {
        "id": document["id"],
        "sha256": document["sha256"],
        "reference": document["reference"],
        "filename": document.get("filename"),
        "sections": [
            {k: s.get(k) for k in ("section_no", "numero", "titre", "texte", "pages_section")}
            for s in sections
        ],
    }
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()
    return hashlib.sha256(encoded).hexdigest()


def cps_chunks(document: dict, sections: list[dict]) -> list[dict]:
    """Les sections sont déjà extraites : aucun PDF, OCR ou LLM n'est appelé."""
    if document.get("doc_type") != "CPS" or not sections:
        raise BackendError("CPS_SECTIONS_REQUIRED")
    if type(document.get("id")) is not int or document["id"] < 1:
        raise BackendError("INVALID_DOCUMENT_ID")
    if not document.get("reference") or not re.fullmatch(
        r"[a-f0-9]{64}", document.get("sha256", "")
    ):
        raise BackendError("INVALID_DOCUMENT_METADATA")
    numbers = [s.get("section_no") for s in sections]
    if any(type(n) is not int or n < 1 for n in numbers) or numbers != sorted(set(numbers)):
        raise BackendError("INVALID_SECTION_ORDER")
    version = fingerprint(document, sections)
    chunks = []
    for section in sections:
        text = section.get("texte")
        if not isinstance(text, str) or not text.strip():
            raise BackendError("EMPTY_SECTION")
        for seq, part in enumerate(fit_budget(text.strip())):
            article = str(section.get("numero") or f"section {section['section_no']}")
            chunks.append(
                {
                    "_id": f"cps:{document['id']}:{section['section_no']}:{seq}",
                    "rag_app": CPS_APP,
                    "pipeline_version": CPS_VERSION,
                    "kind": "chunk",
                    "type": "cps",
                    "corpus": f"cps:{document['reference']}",
                    "document_id": document["id"],
                    "document_sha256": document["sha256"],
                    "snapshot_sha256": version,
                    "reference": document["reference"],
                    "filename": document.get("filename"),
                    "source": f"CPS — {document['reference']} — "
                    f"{document.get('filename') or 'document'}",
                    "section_no": section["section_no"],
                    "numero": section.get("numero"),
                    "titre": section.get("titre"),
                    "article": article,
                    "page": section.get("pages_section"),
                    "chunk_index": seq,
                    "text": part,
                    "text_sha256": hashlib.sha256(part.encode()).hexdigest(),
                    "legal_validation": "document_contractuel_non_valide_juridiquement",
                }
            )
    return chunks


def manifest_for(document: dict, sections: list[dict], chunks: list[dict]) -> dict:
    return {
        "_id": f"cps:{document['id']}:manifest",
        "rag_app": CPS_APP,
        "pipeline_version": CPS_VERSION,
        "kind": "manifest",
        "type": "cps",
        "status": "ready",
        "document_id": document["id"],
        "document_sha256": document["sha256"],
        "reference": document["reference"],
        "snapshot_sha256": fingerprint(document, sections),
        "chunk_count": len(chunks),
    }


def ingest_cps(repository, store, document_id: int) -> dict:
    """Un verrou Postgres sérialise les workers ; aucun statut ready avant le succès."""
    started = time.monotonic()
    run_id = f"rag:cps:{document_id}:{uuid4()}"
    report = {
        "run_id": run_id,
        "document_id": document_id,
        "status": "failed",
        "upserted": 0,
        "skipped": 0,
        "nb_chunks": 0,
        "vector_dim": 1024,
    }
    # session() valide et verrouille le document, puis commit statut + run_logs ensemble.
    with repository.session(document_id) as session:
        document, sections = session.snapshot()
        if document["statut"] not in ("extracted", "ready"):
            return {**report, "status": "skipped", "error": "DOCUMENT_NOT_EXTRACTED"}
        try:
            store.inspect()
            chunks = cps_chunks(document, sections)
            report.update(
                nb_chunks=len(chunks),
                source=chunks[0]["source"],
                tokens=sum(token_count(c["text"]) for c in chunks),
            )
            for chunk in chunks:
                written = store.put_cps(chunk)
                report["upserted" if written else "skipped"] += 1
            manifest = manifest_for(document, sections, chunks)
            store.verify_chunks(chunks)
            store.put_cps(manifest)
            store.verify_cps(manifest, chunks)
            session.finish("ready", None, run_id, report.get("tokens", 0))
            report["status"] = "ready"
        except (BackendError, ValueError) as exc:
            # Aucun message d'exception externe/secret n'est journalisé.
            code = str(exc) if isinstance(exc, BackendError) else "CPS_VALIDATION_FAILED"
            session.finish("echec", code, run_id, report.get("tokens", 0))
            report["error"] = code
    report["duration_seconds"] = round(time.monotonic() - started, 3)
    return report
