"""Aligne la config MCP Agentic avec l'URL ngrok locale en cours.

Usage :
    py -3.13 patch_mcp_url.py            # base-connaissances (port 8203)
    py -3.13 patch_mcp_url.py 8201 base-donnees

Le tunnel ngrok gratuit change d'URL à chaque redémarrage : ce script lit
l'URL publique dans l'API locale ngrok (http://127.0.0.1:4040), puis patch la
configuration du serveur MCP hébergé sur la plateforme Agentic.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.request
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]


def charger_env(chemin: Path) -> None:
    if not chemin.is_file():
        return
    for ligne in chemin.read_text(encoding="utf-8-sig").splitlines():
        ligne = ligne.strip()
        if ligne and not ligne.startswith("#") and "=" in ligne:
            cle, valeur = ligne.split("=", 1)
            os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


def url_ngrok(port: str) -> str:
    with urllib.request.urlopen("http://127.0.0.1:4040/api/tunnels", timeout=10) as rep:
        tunnels = json.loads(rep.read().decode("utf-8"))["tunnels"]
    for tunnel in tunnels:
        if tunnel.get("config", {}).get("addr", "").endswith(":" + port):
            return tunnel["public_url"].rstrip("/") + "/mcp"
    raise RuntimeError(f"aucun tunnel ngrok pour le port {port}")


def principal() -> int:
    port = sys.argv[1] if len(sys.argv) > 1 else "8203"
    nom = sys.argv[2] if len(sys.argv) > 2 else "base-connaissances"

    charger_env(RACINE / "02-backend" / ".env")
    dossier_mcp = RACINE / "05-mcp-server" / {
        "8201": "base-donnees",
        "8202": "portail-marches",
        "8203": "base-connaissances",
    }.get(port, nom)
    charger_env(dossier_mcp / ".env")

    jeton = os.environ.get("AGENTIC_API_KEY")
    base = os.environ.get("AGENTIC_BASE_URL", "https://stg-agentic.abafusion.ai")
    cle_mcp = os.environ.get("MCP_AUTH_TOKEN", "")
    if not jeton:
        print("AGENTIC_API_KEY manquant", file=sys.stderr)
        return 2

    url = url_ngrok(port)
    corps = json.dumps({
        "url": url,
        "headers": {"X-API-Key": cle_mcp} if cle_mcp else {},
    }).encode("utf-8")
    requete = urllib.request.Request(
        base.rstrip("/") + "/api/v2/mcp/servers/" + nom,
        data=corps, method="PATCH",
        headers={"Authorization": "Bearer " + jeton,
                 "Content-Type": "application/json",
                 "User-Agent": "Sou9na-MCP-Patch/1.0"},
    )
    with urllib.request.urlopen(requete, timeout=30) as reponse:
        print(reponse.read().decode("utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(principal())
