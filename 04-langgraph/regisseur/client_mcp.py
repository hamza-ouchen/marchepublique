# ═══════════════════════════════════════════════════════════════════
# SOU9NA — RÉGISSEUR · client MCP (base-donnees)
# Deux modes :
#   LOCAL (défaut) : sous-processus stdio (base-donnees/serveur.py)
#   DISTANT : variables MCP_BASE_DONNEES_URL + MCP_AUTH_TOKEN
#             (StreamableHTTP, « Authorization: Bearer <token> »)
# Si DATABASE_URL est absent → mode « mémoire » (tests, CI).
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

APPELANT = "RÉGISSEUR"          # périmètre vérifié côté MCP : run_logs only


class ClientMCPRegisseur:
    """Accède à base-donnees — stdio en local, StreamableHTTP en distant."""

    def __init__(self, chemin_serveur: str | None = None):
        self.chemin_serveur = chemin_serveur or os.environ.get(
            "MCP_BASE_DONNEES", "../../05-mcp-server/base-donnees/serveur.py"
        )
        self.database_url = os.environ.get("DATABASE_URL", "")
        self.mcp_url = os.environ.get("MCP_BASE_DONNEES_URL", "").rstrip("/")
        self.mcp_token = (
            os.environ.get("MCP_AUTH_TOKEN", "").strip()
            or os.environ.get("MCP_BASE_DONNEES_TOKEN", "").strip()
        )
        self.memoire: dict[str, list[dict]] = {}

    # ── modes ───────────────────────────────────────────────────────
    @property
    def disponible(self) -> bool:
        return bool(self.database_url) and Path(self.chemin_serveur).exists()

    @property
    def distant(self) -> bool:
        return bool(self.mcp_url)

    def disponible_distant(self) -> bool:
        return bool(self.mcp_url and self.mcp_token)

    async def _appeler(self, outil: str, arguments: dict) -> dict:
        if self.disponible_distant():
            return await self._appel_distant(outil, arguments)
        params = StdioServerParameters(
            command="python",
            args=[self.chemin_serveur],
            env={"DATABASE_URL": self.database_url},
        )
        async with stdio_client(params) as (lire_flux, ecrire_flux):
            async with ClientSession(lire_flux, ecrire_flux) as session:
                await session.initialize()
                resultat = await session.call_tool(outil, arguments)
                return json.loads(resultat.content[0].text)

    async def _appel_distant(self, outil: str, arguments: dict) -> dict:
        """StreamableHTTP : initialize → initialized → tools/call (via JSON-RPC).

        Même contrat que les agents de la plateforme Agentic AI (portail mcp.json).
        """
        if not self.mcp_url.endswith("/mcp"):
            endpoint = self.mcp_url + "/mcp" if "/mcp" not in self.mcp_url else self.mcp_url
        else:
            endpoint = self.mcp_url
        headers = {"Content-Type": "application/json",
                   "Accept": "application/json, text/event-stream",
                   "Authorization": f"Bearer {self.mcp_token}"}
        async with httpx.AsyncClient(timeout=30) as cnx:
            init = await cnx.post(endpoint, json={
                "jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05",
                           "capabilities": {},
                           "clientInfo": {"name": "regisseur", "version": "1.0.0"}}},
            headers=headers)
            init.raise_for_status()
            session = init.headers.get("mcp-session-id")
            if session:
                headers["mcp-session-id"] = session
            await cnx.post(endpoint, json={
                "jsonrpc": "2.0", "method": "notifications/initialized"},
                headers=headers)
            reponse = await cnx.post(endpoint, json={
                "jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": outil, "arguments": arguments}},
                headers=headers)
            reponse.raise_for_status()
            corp = reponse.text
            if "data:" in corp:
                corp = "\n".join(l[5:] for l in corp.splitlines() if l.startswith("data:"))
            payload = json.loads(corp)
            if "error" in payload:
                raise RuntimeError(payload["error"])
            texte = payload["result"]["content"][0]["text"]
            return json.loads(texte)

    # ── API utilisée par les nœuds ─────────────────────────────────
    async def ecrire(self, table: str, lignes: list[dict],
                     si_doublon: str = "ignorer") -> dict:
        if self.disponible_distant():
            return await self._appeler("ecrire", {
                "table": table, "lignes": lignes,
                "si_doublon": si_doublon, "appelant": APPELANT})
        if not self.disponible:
            self.memoire.setdefault(table, []).extend(lignes)
            return {"table": table, "mode": "memoire", "ecrites": len(lignes)}
        return await self._appeler("ecrire", {
            "table": table, "lignes": lignes,
            "si_doublon": si_doublon, "appelant": APPELANT,
        })

    async def lire(self, table: str, filtres: dict | None = None,
                   limite: int = 500) -> dict:
        if self.disponible_distant():
            return await self._appeler("lire", {
                "table": table, "filtres": filtres or {},
                "limite": limite, "appelant": APPELANT})
        if not self.disponible:
            lignes = self.memoire.get(table, [])
            if filtres:
                lignes = [l for l in lignes
                          if all(l.get(k) == v for k, v in filtres.items())]
            return {"table": table, "mode": "memoire",
                    "nombre": len(lignes[:limite]), "lignes": lignes[:limite]}
        return await self._appeler("lire", {
            "table": table, "filtres": filtres or {},
            "limite": limite, "appelant": APPELANT,
        })
