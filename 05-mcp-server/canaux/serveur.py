"""
serveur.py — Point d'entrée du serveur MCP "canaux".

ADR-001 v2.6 : ce serveur est l'UNIQUE passerelle d'émission sortante
(WhatsApp + Email) pour tout le système Sou9na. Expose 3 outils MCP :

  - envoyer_whatsapp    : envoie un message WhatsApp via un gabarit
  - envoyer_email       : envoie un email via un gabarit
  - verifier_templates  : liste les gabarits disponibles (lecture seule)

Transport : stdio (FastMCP) — appelé par les agents (CONCIERGE, etc.)
comme un outil MCP standard, pas comme une API HTTP.
"""

import os
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from client_brevo import BrevoError, envoyer_template_email
from client_whatsapp import WhatsAppError, envoyer_template_whatsapp
from gabarits import GABARITS, obtenir_gabarit
from journal import journaliser_tentative
from securite import SecuriteError, marquer_succes, verifier_envoi


def _charger_env(chemin: Path) -> None:
    """Charge .env sans jamais écraser une variable déjà définie."""
    if not chemin.exists():
        return
    for brute in chemin.read_text(encoding="utf-8-sig").splitlines():
        ligne = brute.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        # Supprimer les commentaires en fin de ligne (ex: "10   # ex: ...")
        valeur = re.split(r"\s+#", valeur, maxsplit=1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(cle.strip(), valeur)


_charger_env(Path(__file__).with_name(".env"))

_mode = os.environ.get("MCP_TRANSPORT", "stdio")
_port = int(os.environ.get("FASTMCP_PORT", "8204"))
_host = os.environ.get("FASTMCP_HOST", "127.0.0.1")

_auth_token = (
    os.environ.get("MCP_AUTH_TOKEN", "").strip()
    or os.environ.get("FASTMCP_AUTH_TOKEN", "").strip()
)

_kwargs = {"host": _host, "port": _port}
if _mode in ("sse", "streamable-http"):
    from mcp.server.transport_security import TransportSecuritySettings
    _kwargs["transport_security"] = TransportSecuritySettings(enable_dns_rebinding_protection=False)

mcp = FastMCP("canaux", **_kwargs)

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
            )
            if not key or key != self.api_key:
                return JSONResponse(
                    {"error": "unauthorized", "detail": "Clé API manquante ou invalide"},
                    status_code=401,
                )
        return await call_next(request)


@mcp.tool()
async def envoyer_whatsapp(
    destinataire: str,
    nom_gabarit: str,
    variables: dict[str, str],
    ref: str,
) -> dict:
    """Envoie un message WhatsApp template à un destinataire.

    - destinataire : numéro WhatsApp au format international
    - nom_gabarit   : nom du gabarit (voir verifier_templates)
    - variables     : valeurs des variables du gabarit
    - ref           : identifiant unique de cette demande d'envoi
                      (idempotence — réutiliser le même ref sur un
                      retry ne renverra PAS un 2e message)
    """
    try:
        verifier_envoi(nom_gabarit, variables, destinataire, ref)
    except SecuriteError as exc:
        journaliser_tentative(
            "envoyer_whatsapp", destinataire, nom_gabarit, ref,
            statut="rejet_securite", details=str(exc),
        )
        return {"succes": False, "erreur": str(exc)}

    try:
        # WhatsApp utilise des paramètres POSITIONNELS ({{1}}, {{2}}, ...) :
        # on réordonne les variables selon l'ordre déclaré dans le gabarit,
        # indépendamment de l'ordre fourni par l'appelant.
        gabarit = obtenir_gabarit(nom_gabarit)
        variables_ordonees = {name: variables[name] for name in gabarit.variables}
        resultat = await envoyer_template_whatsapp(
            destinataire, nom_gabarit, variables_ordonees, langue=gabarit.langue
        )
    except WhatsAppError as exc:
        journaliser_tentative(
            "envoyer_whatsapp", destinataire, nom_gabarit, ref,
            statut="echec_api", details=str(exc),
        )
        return {"succes": False, "erreur": str(exc)}

    marquer_succes(destinataire, ref)
    journaliser_tentative(
        "envoyer_whatsapp", destinataire, nom_gabarit, ref,
        statut="succes", details=str(resultat),
    )
    return {"succes": True, "resultat": resultat}


@mcp.tool()
async def envoyer_email(
    destinataire: str,
    nom_gabarit: str,
    variables: dict[str, str],
    ref: str,
) -> dict:
    """Envoie un email template à un destinataire.

    Mêmes paramètres que envoyer_whatsapp. Contrairement à WhatsApp,
    le remplissage des variables dans le gabarit est fait ICI (en
    Python) avant l'appel à Brevo, car Brevo n'a pas de notion de
    "gabarit canaux" — il reçoit un sujet/corps déjà complets.
    """
    try:
        verifier_envoi(nom_gabarit, variables, destinataire, ref)
    except SecuriteError as exc:
        journaliser_tentative(
            "envoyer_email", destinataire, nom_gabarit, ref,
            statut="rejet_securite", details=str(exc),
        )
        return {"succes": False, "erreur": str(exc)}

    gabarit = obtenir_gabarit(nom_gabarit)
    # TODO(Ayoub) : remplacer par de vrais textes/sujets par gabarit
    # (actuellement un texte générique de démonstration).
    sujet = f"Sou9na — {gabarit.description}"
    corps_html = "<p>" + " ".join(f"{k}: {v}" for k, v in variables.items()) + "</p>"

    try:
        resultat = await envoyer_template_email(destinataire, sujet, corps_html)
    except BrevoError as exc:
        journaliser_tentative(
            "envoyer_email", destinataire, nom_gabarit, ref,
            statut="echec_api", details=str(exc),
        )
        return {"succes": False, "erreur": str(exc)}

    marquer_succes(destinataire, ref)
    journaliser_tentative(
        "envoyer_email", destinataire, nom_gabarit, ref,
        statut="succes", details=str(resultat),
    )
    return {"succes": True, "resultat": resultat}


@mcp.tool()
def verifier_templates() -> dict:
    """Liste les gabarits disponibles (lecture seule, pas d'envoi).

    Utile pour qu'un agent appelant sache quels gabarits/variables
    existent avant de tenter un envoi.
    """
    return {
        nom: {
            "canal": g.canal,
            "variables": list(g.variables),
            "description": g.description,
        }
        for nom, g in GABARITS.items()
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
        uvicorn.run(combined, host=_host, port=_port, log_level="info")
    else:
        mcp.run(transport=transport)
