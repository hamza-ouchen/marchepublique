# =====================================================================
# JUGE — serveur A2A (port 8103)
# Statue sur les scores : GO / A_ETUDIER / NO_GO, avec justifications.
# Réutilise le moteur déterministe existant sans duplication de logique.
# =====================================================================
from __future__ import annotations

import os
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RACINE / "04-langgraph"))
sys.path.insert(0, str(_RACINE / "04-langgraph" / "juge"))

from a2a_env import charger_env  # noqa: E402

charger_env()

import juge  # noqa: E402
from a2a_agent import creer_app  # noqa: E402


def _statuer(donnees: dict) -> dict:
    company = donnees.get("company_id") or os.environ["SOU9NA_CRON_COMPANY"]
    rapport = juge.juger(donnees["date"], company)
    rapport["request_id"] = donnees.get("request_id")
    return rapport


app = creer_app(
    "JUGE",
    {"statuer": _statuer},
    "Verdicts GO / A_ETUDIER / NO_GO avec références réglementaires.",
)
