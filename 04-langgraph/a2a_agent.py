# =====================================================================
# SOU9NA — mini-SDK A2A pour les agents locaux
# Contrat identique à celui du RÉGISSEUR : JSON-RPC 2.0 `message/send`,
# en-tête `X-Internal-Token` (A2A_TOKEN), carte sur
# `/.well-known/agent-card.json`. Les handlers sync tournent dans un
# threadpool : le scrape / les PDF / le scoring ne bloquent pas l'event-loop.
# =====================================================================
from __future__ import annotations

import inspect
import os
import re
import uuid
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

from a2a_env import charger_env

Handler = Callable[[dict[str, Any]], Any]


class RequeteA2A(BaseModel):
    jsonrpc: str = "2.0"
    id: str | None = None
    method: str
    params: dict[str, Any]


def _slug(nom: str) -> str:
    return re.sub(r"[^A-Z0-9]+", "_", nom.upper().replace("É", "E").replace("È", "E"))


def _extraire_data(params: dict[str, Any]) -> dict[str, Any]:
    try:
        message = params.get("message", {})
        for part in message.get("parts", []):
            if part.get("kind") == "data":
                return part.get("data", {})
    except Exception:
        pass
    raise HTTPException(status_code=400, detail="message.parts[].data attendu")


def _succes(identifiant: str | None, donnees: dict[str, Any]) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": identifiant,
        "result": {"artifacts": [{"parts": [{"kind": "data", "data": donnees}]}]},
    }


def creer_app(nom: str, competences: dict[str, Handler],
              description: str = "") -> FastAPI:
    """Fabrique le serveur A2A d'un agent local."""
    charger_env()
    token = os.getenv("A2A_TOKEN", "")
    slug = _slug(nom)

    app = FastAPI(title=f"SOU9NA — {nom}", version="1.0.0")

    @app.get("/health")
    def sante() -> dict[str, Any]:
        return {"statut": "ok", "agent": nom, "competences": sorted(competences)}

    @app.get("/.well-known/agent-card.json")
    def carte() -> dict[str, Any]:
        port = os.getenv(f"{slug}_PORT", "8100")
        url = os.getenv(f"{slug}_URL", f"http://127.0.0.1:{port}")
        return {
            "name": nom,
            "description": description,
            "url": url,
            "version": "1.0.0",
            "securitySchemes": {
                "internal-token": {"type": "apiKey", "in": "header",
                                   "name": "X-Internal-Token"}},
            "security": [{"internal-token": []}],
            "defaultInputModes": ["application/json"],
            "defaultOutputModes": ["application/json"],
            "skills": [{"id": identifiant, "name": identifiant}
                       for identifiant in competences],
        }

    @app.post("/")
    async def message_send(requete: RequeteA2A,
                           x_internal_token: str | None = Header(default=None)):
        if token and x_internal_token != token:
            raise HTTPException(status_code=403, detail="token interne invalide")
        if requete.method != "message/send":
            return {"jsonrpc": "2.0", "id": requete.id,
                    "error": {"code": -32601,
                              "message": f"méthode inconnue : {requete.method}"}}

        donnees = _extraire_data(requete.params)
        message = requete.params.get("message", {})
        skill = (message.get("metadata", {}).get("skill_id")
                 or donnees.get("competence") or donnees.get("skill"))
        handler = competences.get(skill)
        if handler is None:
            return {"jsonrpc": "2.0", "id": requete.id,
                    "error": {"code": -32601,
                              "message": f"compétence inconnue : {skill!r} — "
                                         f"disponibles : {sorted(competences)}"}}

        # Contexte de traçabilité A2A (enveloppe commune cahier §5.1)
        donnees.setdefault("request_id", str(uuid.uuid4()))
        try:
            if inspect.iscoroutinefunction(handler):
                resultat = await handler(donnees)
            else:
                resultat = await run_in_threadpool(handler, donnees)
        except Exception as exc:  # mode réel : erreur brute, jamais de bluff
            return {"jsonrpc": "2.0", "id": requete.id,
                    "error": {"code": -32000,
                              "message": f"{type(exc).__name__}: {exc}"}}
        return _succes(requete.id, resultat)

    return app
