# =====================================================================
# CONCIERGE — serveur A2A (port 8104)
# Réponse déterministe et citée, partagée avec FastAPI.
# =====================================================================
from __future__ import annotations

import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RACINE / "04-langgraph"))
sys.path.insert(0, str(_RACINE / "02-backend"))

from a2a_agent import creer_app  # noqa: E402
import chat  # noqa: E402


def _discuter(donnees: dict) -> dict:
    message = str(donnees.get("message") or "")
    company = donnees.get("company_id") or "EXPLEO-IT-001"
    resultat = chat.repondre(message, company, donnees.get("date"))
    resultat["request_id"] = donnees.get("request_id")
    resultat["canal"] = donnees.get("canal", "dashboard")
    return resultat


app = creer_app(
    "CONCIERGE",
    {"discuter": _discuter},
    "Conversation citée (client RLS company_id / visiteur FAQ) — aucun envoi direct.",
)
