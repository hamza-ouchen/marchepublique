# ═══════════════════════════════════════════════════════════════════
# SOU9NA — MCP « portail-marches » · serveur (transport stdio)
# Un seul outil : rechercher_avis(date_iso, mode).
# Le portail n'est jamais appelé par un autre agent ni sur demande client.
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime as dt
import os
from pathlib import Path

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import client_portail


def _charger_env(chemin: Path) -> None:
    """Charge .env sans jamais écraser une variable déjà définie."""
    if not chemin.exists():
        return
    for brute in chemin.read_text(encoding="utf-8-sig").splitlines():
        ligne = brute.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


_charger_env(Path(__file__).with_name(".env"))

_mode = os.environ.get("MCP_TRANSPORT", "stdio")
_port = int(os.environ.get("FASTMCP_PORT", "8202"))
_kwargs = {"host": os.environ.get("FASTMCP_HOST", "127.0.0.1"), "port": _port}
if _mode in ("sse", "streamable-http"):
    _kwargs["transport_security"] = TransportSecuritySettings(enable_dns_rebinding_protection=False)

_auth_token = (
    os.environ.get("MCP_AUTH_TOKEN", "").strip()
    or os.environ.get("FASTMCP_AUTH_TOKEN", "").strip()
)

class _StaticTokenVerifier:
    def __init__(self, token: str):
        self._token = token
    async def verify_token(self, token: str):
        if self._token and token == self._token:
            return AccessToken(token=token, client_id="sou9na-platform",
                               scopes=["mcp"], resource=None)
        return None

if _mode in ("sse", "streamable-http") and _auth_token:
    _kwargs["token_verifier"] = _StaticTokenVerifier(_auth_token)
    _kwargs["auth"] = AuthSettings(
        issuer_url=f"http://127.0.0.1:{_port}/",
        required_scopes=["mcp"],
        resource_server_url=f"http://127.0.0.1:{_port}/",
    )

mcp = FastMCP("portail-marches", **_kwargs)


@mcp.tool()
def rechercher_avis(date_iso: str, mode: str | None = None) -> dict:
    """Renvoie les pages brutes du portail pour la date donnée (≈ 135 avis/jour).

    date_iso : "2026-11-17". mode : "portail" (réel) ou "demo" (fixtures).
    Aucune extraction ici — l'agent INSPECTEUR structure les pages.
    """
    # Validation d'entrée (règle de plausibilité — zéro confiance sur l'entrée).
    try:
        dt.date.fromisoformat(date_iso)
    except ValueError:
        return {"erreur": "date_invalide",
                "detail": f"date_iso doit être ISO 8601 (YYYY-MM-DD), reçu : {date_iso!r}"}
    if mode is not None and mode not in ("portail", "demo"):
        return {"erreur": "mode_invalide", "detail": "mode : portail | demo"}

    return client_portail.rechercher(date_iso, mode)


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
