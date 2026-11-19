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
    mcp.run(transport=transport)
