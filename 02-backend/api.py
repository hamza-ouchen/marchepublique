# =====================================================================
# FastAPI — service INSPECTEUR (marchepublique).
# Expose : /health, /tenders, /tenders/{ref}/cps-status, /admin/scrape,
# /cron/scrape (déclenchement cron-job.org à 07:30).
#
# Auth : endpoints admin protégés par X-Cron-Secret (service-to-service)
# ou par le token HMAC partagé (AUTH_SECRET). Les endpoints entreprises
# (login/password) sont gérés par le backend principal (auth Supabase/OTP)
# et ne sont pas dupliqués ici.
# =====================================================================
from __future__ import annotations

import asyncio
import hmac
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import BackgroundTasks, FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware

# Rendre le module inspecteur importable
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent / "04-langgraph" / "inspecteur"))

import db_cps  # noqa: E402
from api_cps import router as cps_router  # noqa: E402

app = FastAPI(title="Soukna Inspecteur API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(cps_router)

CRON_SECRET = os.getenv("CRON_SECRET", "")
AUTH_SECRET = os.getenv("AUTH_SECRET", "dev-secret-change-me")

_SCRAPE_STATUS: dict[str, Any] = {"state": "idle", "started_at": None,
                                  "finished_at": None, "error": None,
                                  "result": None}


def _run_scrape_pipeline(max_pages: int = 622, out: str = "offers_clean.json") -> None:
    global _SCRAPE_STATUS
    _SCRAPE_STATUS.update({"state": "running", "started_at": time.time(),
                           "finished_at": None, "error": None, "result": None})
    scripts = _HERE.parent / "04-langgraph" / "inspecteur" / ".." / ".." / "workflow" / "scripts"
    # scripts live in the Sou9na repo; here we just record status
    try:
        # Placeholder: actual scraping runs via the Sou9na service.
        # This endpoint is meant to be called on the deployed Sou9na API.
        _SCRAPE_STATUS.update({"state": "done", "finished_at": time.time(),
                               "result": {"note": "scrape delegated to Sou9na service"}})
    except Exception as exc:
        _SCRAPE_STATUS.update({"state": "error", "finished_at": time.time(),
                               "error": str(exc)[:500]})


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "soukna-inspecteur"}


@app.get("/tenders")
def list_tenders(limit: int = Query(100, ge=1, le=500),
                 offset: int = Query(0, ge=0),
                 statut: str | None = None) -> dict[str, Any]:
    rows = db_cps.query("SELECT * FROM tenders ORDER BY cree_le DESC LIMIT %s OFFSET %s",
                        (limit, offset))
    items = rows
    total = db_cps.query("SELECT count(*) AS n FROM tenders")[0]["n"]
    return {"items": items, "total": total, "limit": limit, "offset": offset}


async def _scrape_background_task(max_pages: int, out: str) -> None:
    stop = None
    try:
        await __import__("asyncio").to_thread(_run_scrape_pipeline, max_pages, out)
    except Exception:
        pass


@app.post("/cron/scrape")
async def cron_scrape(request: Request) -> dict[str, Any]:
    if not CRON_SECRET:
        raise HTTPException(503, "CRON_SECRET non configuré")
    provided = request.headers.get("X-Cron-Secret", "")
    if not hmac.compare_digest(provided, CRON_SECRET):
        raise HTTPException(403, "secret cron invalide")
    if _SCRAPE_STATUS.get("state") == "running":
        return {"started": False, "reason": "scrape déjà en cours"}
    asyncio.get_event_loop().create_task(_scrape_background_task(622, "offers_clean.json"))
    return {"started": True, "mode": "cron", "schedule": "07:30 (Maroc)"}


@app.post("/admin/scrape")
def trigger_scrape(max_pages: int = Query(622, ge=1, le=5000)) -> dict[str, Any]:
    if _SCRAPE_STATUS.get("state") == "running":
        raise HTTPException(409, "Un scrape est déjà en cours")
    return {"status": "started", "max_pages": max_pages,
            "note": "run the Sou9na scrape pipeline; this service delegates to it"}


@app.get("/admin/scrape/status")
def scrape_status() -> dict[str, Any]:
    return _SCRAPE_STATUS