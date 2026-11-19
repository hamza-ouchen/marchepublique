# ═══════════════════════════════════════════════════════════════════
# SOU9NA — RÉGISSEUR · les 3 passes de garde (avant l'orchestrateur)
# 100 % déterministe — aucun LLM ici (les gates propagent la confiance,
# jamais l'invention). En cas de rejet : arrêt immédiat + journalisation.
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import datetime as dt
import re
from typing import Any

from etat_run import EtatRun

MODES_VALIDES = {"cron", "manuel", "backfill"}

# Heuristiques d'injection (captures les framings usuels — red team 07-securite)
PATTERNS_INJECTION = [
    r"ignore\s+(all\s+)?(previous|prior)\s+(instructions|prompts)",
    r"act\s+as(\s+if|\s+though)?\s",
    r"you\s+are\s+now\b",
    r"disregard\b",
    r"\bsystem\s*:\s*",
    r"system\s+prompt",
    r"\bjailbreak\b",
    r"\boverride\b",
    r"\bdeveloper\s+mode\b",
    r"\bsudo\b",
    r"<<\s*SYS\s*>>",
    r"\[\s*inst\s*\]",
]
MSG_MAX = 2000


def valider_entree(etat: EtatRun) -> dict:
    """Porte 1 — structure : mode connu, date ISO, run_id présent."""
    erreurs: list[str] = []
    mode = etat.get("mode", "")
    if mode not in MODES_VALIDES:
        erreurs.append(f"mode inconnu : {mode!r} (attendu : {sorted(MODES_VALIDES)})")
    try:
        dt.date.fromisoformat(str(etat.get("date", "")))
    except ValueError:
        erreurs.append(f"date invalide : {etat.get('date')!r} (attendu : YYYY-MM-DD)")
    if not etat.get("run_id"):
        erreurs.append("run_id manquant — le RÉGISSEUR requiert un identifiant de run")
    if erreurs:
        return {"gates": ["valider_entree: ÉCHEC"], "rejete": True, "erreurs": erreurs,
                "statut": "rejete"}
    return {"gates": [f"valider_entree: OK (mode={mode})"]}


def sanitariser_entree(etat: EtatRun) -> dict:
    """Porte 2 — contenu : longueur, caractères de contrôle, injection heuristique."""
    if etat.get("rejete"):
        return {"gates": ["sanitariser_entree: SAUTÉE (rejet amont)"]}
    msg = str(etat.get("message", "") or "")
    erreurs: list[str] = []
    if len(msg) > MSG_MAX:
        erreurs.append(f"message trop long ({len(msg)} car. > {MSG_MAX})")
    if any(ord(c) < 32 and c not in "\n\r\t" for c in msg):
        erreurs.append("caractères de contrôle non imprimables")
    for motif in PATTERNS_INJECTION:
        if re.search(motif, msg, re.I):
            erreurs.append("motif d'injection détecté")
            break
    if erreurs:
        return {"gates": ["sanitariser_entree: REJET (injection / abus)"],
                "rejete": True, "erreurs": erreurs, "statut": "rejete"}
    return {"gates": ["sanitariser_entree: OK"]}


INTENTIONS: dict[str, list[str]] = {
    "opportunites": ["offre", "opportunité", "opportunites", "match", "score"],
    "digest":       ["digest", "quotidien", "resumé", "bilan", "rapport"],
    "sante":        ["sante", "portail", "panne", "degrad", "ping"],
    "profil":       ["profil", "compte", "ice", "capacite"],
}


def classer_intention(etat: EtatRun) -> dict:
    """Porte 3 — intention : classification par règles (mot-clé).

    Cron/backfill = intention « digest » par construction. Pour un chat, tout
    message non classé part en `hors_perimetre` → HITL 3 (jamais interprété).
    """
    if etat.get("rejete"):
        return {"gates": ["classer_intention: SAUTÉE (rejet amont)"]}

    mode = etat.get("mode", "cron")
    if mode in ("cron", "backfill"):
        return {"intention": "digest", "gates": ["classer_intention: OK → intention=digest (pipeline)"]}

    msg = str(etat.get("message", "") or "").lower()
    for intention, mots in INTENTIONS.items():
        if any(m in msg for m in mots):
            tag = f"classer_intention: OK → intention={intention}"
            return {"intention": intention, "gates": [tag]}
    return {"intention": "hors_perimetre",
            "gates": ["classer_intention: aucune règle → hors_perimetre (HITL 3)"]}


def rejet_gate(etat: EtatRun) -> dict:
    """Nœud terminus : le refus est journalisé, jamais silencieux."""
    nvl = dict(etat)
    nvl["statut"] = "rejete"
    return {"etapes": [f"REJET : {' | '.join(nvl.get('erreurs', []))}"],
            "statut": "rejete"}
