# =====================================================================
# Endpoints CPS (lecture seule + signal ready) — module inspecteur.
# À monter dans l'app FastAPI principale (api.py) via include_router.
# =====================================================================
from __future__ import annotations

import os
from typing import Any

from fastapi import APIRouter, HTTPException, Request

import db_cps

router = APIRouter(prefix="/tenders", tags=["cps"])


@router.get("/{reference:path}/cps-status")
def get_cps_status(reference: str) -> dict[str, Any]:
    if not db_cps.tenders_get(reference):
        raise HTTPException(404, "Tender introuvable")
    return db_cps.cps_status(reference)


@router.post("/internal/cps/{document_id}/ready")
async def mark_cps_ready(document_id: int, request: Request) -> dict[str, Any]:
    secret = os.getenv("CRON_SECRET", "")
    provided = request.headers.get("X-Cron-Secret", "") or request.headers.get("X-Service-Secret", "")
    if not secret or provided != secret:
        raise HTTPException(403, "secret service invalide")
    db_cps.tender_document_mark_ready(document_id)
    return {"document_id": document_id, "statut": "ready"}


@router.post("/{reference:path}/cps-ready")
def mark_tender_cps_ready(reference: str) -> dict[str, Any]:
    doc = db_cps.tender_document_by_reference(reference)
    if not doc:
        raise HTTPException(404, "Aucun document CPS pour ce tender")
    if doc.get("statut") == "stored":
        raise HTTPException(409, "Le document doit être extrait avant d'être prêt")
    db_cps.tender_document_mark_ready(doc["id"])
    return {"reference": reference, "document_id": doc["id"], "statut": "ready"}
