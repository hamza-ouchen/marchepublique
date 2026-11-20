# ═══════════════════════════════════════════════════════════════════
# SOU9NA — RÉGISSEUR · point d'entrée CLI
#   python run.py --mode cron    --demo
#   python run.py --mode manuel
#   python run.py --mode backfill
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import sys

from client_mcp import ClientMCPRegisseur
from etat_run import nouvel_etat
from graphe import construire_graphe
from noeuds import nouveau_run_id


async def executer(mode: str, date: str, demo: bool) -> dict:
    client = ClientMCPRegisseur()
    if demo:
        client.database_url = ""                      # forcer le mode mémoire
    etat_initial = nouvel_etat(mode, date, demo, nouveau_run_id(mode, date))
    app = construire_graphe(client)
    etat_final = await app.ainvoke(etat_initial)
    return dict(etat_final)


def principal() -> int:
    parser = argparse.ArgumentParser(description="RÉGISSEUR — run quotidien / manuel / backfill")
    parser.add_argument("--mode", choices=["cron", "manuel", "backfill"], default="cron")
    parser.add_argument("--date", default=dt.date.today().isoformat())
    parser.add_argument("--demo", action="store_true",
                        help="rapports simulés, écritures en mémoire (tests)")
    args = parser.parse_args()

    demo = args.demo or os.environ.get("MODE_AGENTS", "reel") == "demo"
    if not demo:
        print("Mode reel : les agents seront appelés via A2A "
              "(cartes dans 03-agentic-ai/agent-cards/).")
    etat = asyncio.run(executer(args.mode, args.date, demo))

    print("─" * 60)
    print(f"Run {etat['run_id']} → statut : {etat['statut'].upper()}")
    for etape in etat["etapes"]:
        print(" ·", etape)
    if etat["erreurs"]:
        for err in etat["erreurs"]:
            print(" ⚠ erreur :", err)
        return 1
    if os.environ.get("REGISSEUR_TRACE"):
        print(json.dumps(etat["rapport"], ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(principal())
