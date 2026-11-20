# ═══════════════════════════════════════════════════════════════════
# SOU9NA — RÉGISSEUR · serveur HTTP (Agentic AI endpoint)
# Expose POST / en JSON-RPC 2.0 `message/send` (skill `orchestrer`) —
# même protocole que les autres agents (agent2agent).
# Auth : `X-Internal-Token` (env A2A_TOKEN). Jamais en 0.0.0.0 en prod
# sans VPC/proxy authentifié (Render/service mutualisé avec token).
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException
from pydantic import BaseModel

from client_mcp import ClientMCPRegisseur
from etat_run import nouvel_etat
from graphe import construire_graphe
from noeuds import nouveau_run_id

A2A_TOKEN = os.environ.get("A2A_TOKEN", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")
PORT = int(os.environ.get("PORT", "8100"))

_graph = None      # construit 1× au démarrage
_client = None


@asynccontextmanager
async def lifespan(_app_: FastAPI):
    global _graph, _client
    _client = ClientMCPRegisseur()
    _graph = construire_graphe(_client)
    yield


_app = FastAPI(title="RÉGISSEUR — La Régie", version="1.0.0", lifespan=lifespan)


class RequeteA2A(BaseModel):
    jsonrpc: str = "2.0"
    id: str | None = None
    method: str
    params: dict


async def verifier_token(x_internal_token: str | None = Header(default=None)):
    if A2A_TOKEN and x_internal_token != A2A_TOKEN:
        raise HTTPException(status_code=403, detail="token invalide")


_auth = verifier_token


def _extraction_entree(params: dict) -> dict:
    """Trouve l'objet `data` de la `message` JSON-RPC."""
    try:
        message = params.get("message", {})
        parts = message.get("parts", [])
        for part in parts:
            if part.get("kind") == "data":
                return part.get("data", {})
        raise ValueError("aucune partie kind=data")
    except Exception as err:                       # noqa: BLE001
        raise HTTPException(
            status_code=400,
            detail=f"params_invalides : {err} (attendu : message.parts[].data)",
        )


@_app.post("/")
async def orchestrer(requete: RequeteA2A, _=Depends(_auth)):
    if requete.method != "message/send":
        return {"jsonrpc": "2.0", "id": requete.id,
                "error": {"code": -32601, "message": f"méthode inconnue : {requete.method}"}}

    data = _extraction_entree(requete.params)
    mode = data.get("mode", "cron")
    date = data.get("date") or data.get("date_iso") or ""
    demo = bool(data.get("demo", False))
    msg = str(data.get("message", "") or "")
    run_id = data.get("run_id") or nouveau_run_id(mode, date or "")

    etat = nouvel_etat(mode, date, demo, run_id)
    etat["message"] = msg
    if not DATABASE_URL:
        etat["demo"] = True    # pas de base → jamais d'effets de bord réels

    etat_final = await _graph.ainvoke(etat)

    return {
        "jsonrpc": "2.0",
        "id": requete.id,
        "result": {
            "artifacts": [
                {"parts": [
                    {"kind": "data", "data": {
                        "run_id": etat_final.get("run_id"),
                        "mode": etat_final.get("mode"),
                        "date": etat_final.get("date"),
                        "intention": etat_final.get("intention", "digest"),
                        "gates": etat_final.get("gates", []),
                        "etapes": etat_final.get("etapes", []),
                        "statut": etat_final.get("statut"),
                        "erreurs": etat_final.get("erreurs", []),
                        "rapport": etat_final.get("rapport", {}),
                    }}]}
            ]
        },
    }


if __name__ == "__main__":
    uvicorn.run(_app, host="0.0.0.0", port=PORT, log_level="info")
