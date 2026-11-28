"""Rattrapage immédiat d'une entreprise inscrite en cours de journée.

Lorsqu'un client active son essai à 11h, il ne doit pas attendre le run de 8h
du lendemain : on utilise le Stock d'appels déjà collecté le matin. Ce chemin
est 100 % local et déterministe — aucun flow Agentic n'est appelé ici (la
plateforme n'a de toute façon pas terminé sa fenêtre quotidienne).

Ordre réel : scoring local -> JUGE local -> digest -> distribution locale.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from zoneinfo import ZoneInfo
from pathlib import Path
from typing import Any

_ROOT = Path(__file__).resolve().parents[1]
for _chemin in (
    _ROOT / "03-agentic-ai" / "compagnon",
    _ROOT / "04-langgraph",
    _ROOT / "04-langgraph" / "juge",
):
    _s = str(_chemin)
    if _s not in sys.path:
        sys.path.insert(0, _s)

from app import db  # noqa: E402


def _trace(rapport: dict[str, Any], etape: str, detail: str) -> None:
    rapport["etapes"].append(f"{etape} : {detail}")


def calculer_maintenant(company_id: str, date_cible: str | None = None,
                        avec_distribution: bool = True) -> dict[str, Any]:
    """Score, statue, compose et distribue à partir des offres déjà en base."""
    jour = date_cible or datetime.now(ZoneInfo("Africa/Casablanca")).date().isoformat()
    rapport: dict[str, Any] = {
        "company_id": company_id,
        "date": jour,
        "source": "local_immediate",
        "platform_agentic": "non requis (fenêtre quotidienne 8h non écoulée)",
        "statut": "ok",
        "etapes": [],
    }

    try:
        import score_local
        scores = score_local.run_scoring(company_id, jour, all_open=True)
        rapport["scores"] = scores
        _trace(rapport, "calculer_scores",
               f"{scores.get('scores_ecrits')} scores sur "
               f"{scores.get('tenders_lus')} offres ouvertes ({scores.get('algo_version')})")
        if int(scores.get("scores_ecrits") or 0) <= 0:
            rapport["statut"] = "aucune_offre"
            _trace(rapport, "statuer", "aucun score — verdicts non écrits")
            return rapport
    except Exception as exc:  # noqa: BLE001
        rapport["statut"] = "echec"
        rapport["erreur"] = f"calculer_scores : {type(exc).__name__}: {exc}"
        return rapport

    try:
        import juge
        verdicts = juge.juger(jour, company_id)
        rapport["verdicts"] = verdicts
        _trace(rapport, "statuer",
               f"{verdicts.get('verdicts_ecrits')} verdicts "
               f"(GO {verdicts.get('go')} · À étudier {verdicts.get('a_etudier')} "
               f"· NO-GO {verdicts.get('no_go')})")
    except Exception as exc:  # noqa: BLE001
        rapport["erreur"] = f"statuer : {type(exc).__name__}: {exc}"
        rapport["statut"] = "partiel"

    try:
        import compose_digest
        digest = compose_digest.composer(jour, company_id)
        rapport["digest"] = digest
        _trace(rapport, "composer_digest",
               f"{digest.get('digests_composes')} digests composés")
    except Exception as exc:  # noqa: BLE001
        rapport["erreur"] = f"composer_digest : {type(exc).__name__}: {exc}"
        rapport["statut"] = "partiel"

    if avec_distribution:
        try:
            import distribuer as distribution
            envois = distribution.distribuer(jour, company_id)
            rapport["distribution"] = envois
            _trace(rapport, "distribuer",
                   f"{envois.get('envois_email')} email(s), "
                   f"{envois.get('envois_whatsapp')} WhatsApp "
                   f"(opt-out respecté), HITL {envois.get('hitl_declenches')}")
        except Exception as exc:  # noqa: BLE001
            rapport["erreur"] = f"distribuer : {type(exc).__name__}: {exc}"
            if rapport["statut"] == "ok":
                rapport["statut"] = "partiel"

    try:
        db.audit(company_id, "score_immediate", None,
                 json.dumps(rapport, ensure_ascii=False, default=str)[:500])
    except Exception:  # noqa: BLE001
        pass
    return rapport
