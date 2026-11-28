# =====================================================================
# COMPAGNON — serveur A2A (port 8102)
# Trois passages, trois compétences : calculer_match / composer_digest /
# distribuer_digests. Le scoring est exécuté par le scorer Python interne.
# =====================================================================
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RACINE / "04-langgraph"))
sys.path.insert(0, str(_RACINE / "03-agentic-ai" / "compagnon"))

from a2a_env import charger_env  # noqa: E402

charger_env()

import compose_digest  # noqa: E402
import distribuer  # noqa: E402
import score_local  # noqa: E402
from a2a_agent import creer_app  # noqa: E402


def _company(donnees: dict) -> str:
    return donnees.get("company_id") or os.environ["SOU9NA_CRON_COMPANY"]


def _calculer_match(donnees: dict) -> dict:
    rapport = score_local.run_scoring(_company(donnees), donnees["date"])
    rapport["source"] = "compagnon_local"
    rapport["request_id"] = donnees.get("request_id")
    return rapport


def _calculer_match_agentic_legacy(donnees: dict) -> dict:
    company = _company(donnees)
    date = donnees["date"]
    # Production : le scorer interne est la voie par défaut. Le flow Agentic
    # externe reste activable (SOU9NA_AGENTIC_FLOW=1) mais ne doit jamais
    # ajouter 1000 appels réseau fragiles au chemin quotidien.
    if os.getenv("SOU9NA_AGENTIC_FLOW", "0").lower() in ("1", "true", "oui", "yes"):
        import agentic_flow

        try:
            ok, information = agentic_flow.run_compagnon(company, date)
        except Exception as exc:  # 504 / timeout / panne plateforme
            ok, information = False, f"{type(exc).__name__}: {exc}"
    else:
        ok, information = False, "flow Agentic désactivé (SOU9NA_AGENTIC_FLOW=0)"

    if ok:
        nombre = re.search(r'"scores_ecrits"\s*:\s*(\d+)', information)
        scores_ecrits = int(nombre.group(1)) if nombre else 0
        if scores_ecrits > 0:
            return {
                "scores_ecrits": scores_ecrits,
                "algo_version": "1.0.0",
                "source": "flow_compagnon",
                "detail": information[-600:],
                "request_id": donnees.get("request_id"),
            }

    # Le flow plateforme peut répondre 200 sans écrire de score (base MCP
    # distante, panne partielle, 0 même-domaine). Ce n'est pas une preuve :
    # l'outil interne du COMPAGNON reprend le calcul sur la base réelle.
    rapport = score_local.run_scoring(company, date)
    if ok:
        rapport["detail"] = f"flow sans score — {information[-300:]}"
    else:
        rapport["detail"] = f"flow indisponible — {information[:300]}"
    rapport["request_id"] = donnees.get("request_id")
    return rapport


def _composer_digest(donnees: dict) -> dict:
    rapport = compose_digest.composer(donnees["date"], _company(donnees))
    rapport["request_id"] = donnees.get("request_id")
    return rapport


def _distribuer_digests(donnees: dict) -> dict:
    rapport = distribuer.distribuer(donnees["date"], _company(donnees))
    rapport["request_id"] = donnees.get("request_id")
    return rapport


app = creer_app(
    "COMPAGNON",
    {
        "calculer_match": _calculer_match,
        "composer_digest": _composer_digest,
        "distribuer_digests": _distribuer_digests,
    },
    "Match /100 déterministe, composition FR/AR et distribution via MCP canaux.",
)
