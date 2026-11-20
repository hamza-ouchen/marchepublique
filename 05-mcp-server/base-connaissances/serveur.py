# ═══════════════════════════════════════════════════════════════════
# SOU9NA — MCP « base-connaissances » · serveur
# Un seul outil : chercher(requete, corpus) — contrat J5 (Ouchen + Mhalli).
#
# Transport : stdio (défaut) ou StreamableHTTP (POST /mcp).
# Le fichier .env local est chargé automatiquement (sans écraser l'existant).
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
from pathlib import Path

from mcp.server.auth.provider import AccessToken
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

import moteur_recherche
from moteur_recherche import CORPUS_STATIQUES, NOMBRE_PAR_DEFAUT


def _charger_env(chemin: Path) -> None:
    """Charge .env sans jamais écraser une variable déjà définie."""
    if not chemin.exists():
        return
    for brute in chemin.read_text(encoding="utf-8-sig").splitlines():
        ligne = brute.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        if " #" in valeur:
            valeur = valeur.split(" #", 1)[0]
        valeur = valeur.strip().strip('"').strip("'")
        os.environ.setdefault(cle.strip(), valeur)


_charger_env(Path(__file__).with_name(".env"))

_mode = os.environ.get("MCP_TRANSPORT", "stdio")
_port = int(os.environ.get("FASTMCP_PORT", "8203"))
_kwargs: dict = {"host": os.environ.get("FASTMCP_HOST", "127.0.0.1"), "port": _port}
if _mode in ("sse", "streamable-http"):
    _kwargs["transport_security"] = TransportSecuritySettings(
        enable_dns_rebinding_protection=False
    )

_auth_token = (
    os.environ.get("MCP_AUTH_TOKEN", "").strip()
    or os.environ.get("FASTMCP_AUTH_TOKEN", "").strip()
)

# ── Middleware d'authentification par clé API (en-tête personnalisé) ──
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Vérifie la clé API dans l'en-tête X-API-Key (ou api-mcp-key)."""

    def __init__(self, app, api_key: str):
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request, call_next):
        if self.api_key and request.url.path != "/":
            key = (
                request.headers.get("x-api-key")
                or request.headers.get("api-mcp-key")
                or request.headers.get("authorization", "").replace("Bearer ", "").strip()
            )
            # Auth required: key must be present and valid
            if not key or key != self.api_key:
                return JSONResponse(
                    {"error": "unauthorized", "detail": "Clé API manquante ou invalide"},
                    status_code=401,
                )
        return await call_next(request)

mcp = FastMCP("base-connaissances", **_kwargs)


@mcp.tool()
def chercher(requete: str, corpus: str = "faq", nombre: int = NOMBRE_PAR_DEFAUT) -> dict:
    """Recherche documentaire avec citations obligatoires.

    requete : texte libre (français, arabe ou darija translittérée) ;
    corpus  : "faq" | "reglementation" | "cps:<reference>" ;
    nombre  : 1 à 5 résultats (5 par défaut).

    → passages [{texte, source, article, score}] × 5 maximum.
    Une base vide renvoie `passages: []`, `vide: true` et un `message`
    explicite — jamais une erreur non structurée.
    """
    if not isinstance(requete, str) or not requete.strip():
        return {"erreur": "requete_vide",
                "detail": "la requête ne peut pas être vide",
                "passages": [], "vide": True}
    if not moteur_recherche.corpus_valide(corpus):
        return {
            "erreur": "corpus_invalide",
            "detail": f"corpus : {CORPUS_STATIQUES} ou cps:<reference> — reçu : {corpus!r}",
            "passages": [], "vide": True,
        }
    try:
        return moteur_recherche.chercher(requete.strip(), corpus, nombre)
    except Exception as erreur:                      # filet de sécurité : jamais de 500
        return {
            "erreur": "moteur_indisponible",
            "detail": f"{type(erreur).__name__}: {erreur}",
            "passages": [], "vide": True,
        }


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport in ("sse", "streamable-http"):
        import uvicorn
        from starlette.applications import Starlette

        # Both transports on one port: /mcp (Streamable HTTP) + /sse (legacy SSE)
        http_app = mcp.streamable_http_app()
        sse_app = mcp.sse_app()
        combined = Starlette(
            routes=list(http_app.routes) + list(sse_app.routes),
            lifespan=http_app.router.lifespan_context,
        )
        combined.add_middleware(APIKeyMiddleware, api_key=_auth_token)
        uvicorn.run(combined, host=_kwargs["host"], port=_kwargs["port"], log_level="info")
    else:
        mcp.run(transport=transport)
