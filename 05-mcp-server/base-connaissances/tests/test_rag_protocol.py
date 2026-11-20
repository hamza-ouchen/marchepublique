"""Vrai échange MCP stdio ; absence d'accès Astra = HITL, sans appel réseau."""

import asyncio
import json
import os
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


def test_real_mcp_tool_contract_without_credentials():
    folder = Path(__file__).resolve().parents[1]
    root = folder.parents[1]
    env = {
        key: os.environ[key] for key in ("PATH", "SYSTEMROOT", "TEMP", "TMP") if key in os.environ
    }
    env.update(
        MCP_TRANSPORT="stdio",
        MOTEUR="rag",
        PYTHONIOENCODING="utf-8",
        PYTHONPATH=str(root / "06-connaissances/astra-rag"),
    )

    async def check():
        params = StdioServerParameters(
            command=sys.executable, args=[str(folder / "serveur.py")], cwd=str(folder), env=env
        )
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert "chercher" in [tool.name for tool in tools.tools]
                result = await session.call_tool(
                    "chercher", {"requete": "caution provisoire", "corpus": "reglementation"}
                )
                payload = result.structuredContent
                if payload is None:
                    payload = json.loads(result.content[0].text)
                assert payload["citation_imposee"] and payload["hitl"]
                assert payload["passages"] == [] and payload["erreur"] == "rag_indisponible"

    asyncio.run(asyncio.wait_for(check(), timeout=30))
