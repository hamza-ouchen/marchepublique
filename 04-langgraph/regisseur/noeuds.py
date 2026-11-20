# ═══════════════════════════════════════════════════════════════════
# SOU9NA — RÉGISSEUR · nœuds du graphe (la chaîne du matin, CAS A)
#
# Chaque nœud :
#   1. saute son travail si une erreur est déjà enregistrée (garde-fou) ;
#   2. fait SON travail (et rien que son travail) ;
#   3. renvoie une mise à jour partielle de l'état (etapes / rapport /
#      erreurs). Les données métier circulent par la base — pas ici.
#
# Agents : en mode demo, chaque agent renvoie un rapport simulé cohérent
# (graphe exécutable de bout en bout). En mode réel, brancher ici l'entrée
# de l'agent (HTTP) — le graphe ne change pas.
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import uuid

from a2a_client import appeler_a2a
from etat_run import EtatRun

MODE_AGENTS = os.environ.get("MODE_AGENTS", "demo")


def _garder_fou(etat: EtatRun, nom: str) -> bool:
    """True si le nœud doit sauter (une étape précédente a échoué)."""
    return bool(etat.get("erreurs"))


def _horaire(nom: str) -> str:
    return {"ouvrir_run": "6h00", "collecter": "6h05",
            "calculer_scores": "6h20", "statuer": "7h00",
            "composer_digest": "7h30", "distribuer": "8h00",
            "cloturer_run": "18h00"}[nom]


def _trace(etat: EtatRun, nom: str, detail: str) -> dict:
    return {"etapes": [f"{_horaire(nom)} {nom} : {detail}"]}


# ── Points d'appel agents (brancher les vrais agents ici) ──────────
async def APPEL_INSPECTEUR(etat: EtatRun) -> dict:
    """INSPECTEUR collecte → tenders. Rapport attendu :
    {avis_nouveaux, doublons, rejetes, source}."""
    if etat["demo"]:
        return {"avis_nouveaux": 135, "doublons": 0, "rejetes": 3,
                "source": "demo" if etat["mode"] != "backfill" else "backfill-demo"}
    mode = {"cron": "portail", "manuel": "portail", "backfill": "backfill"}[etat["mode"]]
    return await appeler_a2a("collecte_avis", {"mode": mode, "date": etat["date"]})


async def APPEL_COMPAGNON_SCORES(etat: EtatRun) -> dict:
    """COMPAGNON (1er passage) : Match /100 → scores."""
    if etat["demo"]:
        return {"scores_ecrits": 132, "algo_version": "1.0.0-demo"}
    return await appeler_a2a("calculer_match", {"date": etat["date"]})


async def APPEL_JUGE(etat: EtatRun) -> dict:
    """JUGE : verdicts sur les scores au-dessus du seuil (~75)."""
    if etat["demo"]:
        return {"verdicts_ecrits": 41, "go": 22, "a_etudier": 9, "no_go": 10,
                "seuil": 75}
    return await appeler_a2a("statuer", {"date": etat["date"], "seuil": 75})


async def APPEL_COMPAGNON_DIGEST(etat: EtatRun) -> dict:
    """COMPAGNON (2e passage) : compose les digests (FR+AR), n'envoie pas."""
    if etat["demo"]:
        return {"digests_composes": 24, "bandeau": "essai jour 1 sur 14"}
    return await appeler_a2a("composer_digest", {"date": etat["date"]})


async def APPEL_COMPAGNON_DISTRIBUTION(etat: EtatRun) -> dict:
    """COMPAGNON (8h00) : distribue les digests du jour via MCP canaux."""
    if etat["demo"]:
        return {"envois_whatsapp": 18, "envois_email": 6,
                "hitl_declenches": 2, "statut_envoi": "envoye"}
    return await appeler_a2a("distribuer_digests", {"date": etat["date"]})


# ── Nœuds du graphe ────────────────────────────────────────────────
async def ouvrir_run(etat: EtatRun, client) -> dict:
    """RÉGISSEUR : ouvrir le run (run_logs = « ouvert »)."""
    mise = _trace(etat, "ouvrir_run", "run_logs = ouvert")
    resultat = await client.ecrire("run_logs", [{
        "run_id": etat["run_id"],
        "type": etat["mode"],
        "statut": "ouvert",
    }])
    if "erreur" in resultat:
        mise["erreurs"] = [f"ouvrir_run : {resultat['detail']}"]
    return mise


async def collecter(etat: EtatRun, client) -> dict:
    """INSPECTEUR (6h05) — le SEUL à appeler le portail. En mode backfill :
    tous les avis encore ouverts (une seule fois, idempotence)."""
    if _garder_fou(etat, "collecter"):
        return {"etapes": [f"6h05 collecter : SAUTÉ (erreur amont)"]}
    try:
        rapport = await APPEL_INSPECTEUR(etat)
        await client.ecrire("run_logs", [{
            "run_id": etat["run_id"], "type": etat["mode"], "statut": "ouvert",
            "avis_nouveaux": rapport.get("avis_nouveaux"),
            "doublons": rapport.get("doublons"), "rejetes": rapport.get("rejetes"),
        }], si_doublon="mettre_a_jour")
        trace = f"{rapport.get('avis_nouveaux')} avis (source {rapport.get('source')})"
        return _trace(etat, "collecter", trace) | {"rapport": {"inspecteur": rapport}}
    except Exception as err:                                   # noqa: BLE001
        return {"etapes": ["6h05 collecter : ÉCHEC"], "erreurs": [str(err)]}


async def calculer_scores(etat: EtatRun, client) -> dict:
    """COMPAGNON (6h20) : Match /100 en batch — zéro LLM."""
    if _garder_fou(etat, "calculer_scores"):
        return {"etapes": ["6h20 calculer_scores : SAUTÉ (erreur amont)"]}
    try:
        rapport = await APPEL_COMPAGNON_SCORES(etat)
        return (_trace(etat, "calculer_scores",
                       f"{rapport.get('scores_ecrits')} scores")
                | {"rapport": {"compagnon_scores": rapport}})
    except Exception as err:                                   # noqa: BLE001
        return {"etapes": ["6h20 calculer_scores : ÉCHEC"], "erreurs": [str(err)]}


async def statuer(etat: EtatRun, client) -> dict:
    """JUGE (7h00) : verdicts — Match ≠ verdict (un 96 peut être NO-GO)."""
    if _garder_fou(etat, "statuer"):
        return {"etapes": ["7h00 statuer : SAUTÉ (erreur amont)"]}
    try:
        rapport = await APPEL_JUGE(etat)
        return (_trace(etat, "statuer",
                       f"{rapport.get('verdicts_ecrits')} verdicts "
                       f"(GO {rapport.get('go')} · À ÉTUDIER {rapport.get('a_etudier')}"
                       f" · NO-GO {rapport.get('no_go')})")
                | {"rapport": {"juge": rapport}})
    except Exception as err:                                   # noqa: BLE001
        return {"etapes": ["7h00 statuer : ÉCHEC"], "erreurs": [str(err)]}


async def composer_digest(etat: EtatRun, client) -> dict:
    """COMPAGNON (7h30) : compose les digests — n'envoie JAMAIS."""
    if _garder_fou(etat, "composer_digest"):
        return {"etapes": ["7h30 composer_digest : SAUTÉ (erreur amont)"]}
    try:
        rapport = await APPEL_COMPAGNON_DIGEST(etat)
        return (_trace(etat, "composer_digest",
                       f"{rapport.get('digests_composes')} digests composés")
                | {"rapport": {"compagnon_digest": rapport}})
    except Exception as err:                                   # noqa: BLE001
        return {"etapes": ["7h30 composer_digest : ÉCHEC"], "erreurs": [str(err)]}


async def distribuer(etat: EtatRun, client) -> dict:
    """COMPAGNON (8h00) : distribution via MCP canaux (ADR-001 / v2.6)."""
    if _garder_fou(etat, "distribuer"):
        return {"etapes": ["8h00 distribuer : SAUTÉ (erreur amont)"]}
    try:
        rapport = await APPEL_COMPAGNON_DISTRIBUTION(etat)
        return (_trace(etat, "distribuer",
                       f"{rapport.get('envois_whatsapp') + rapport.get('envois_email')}"
                       f" envois · HITL {rapport.get('hitl_declenches')}")
                | {"rapport": {"compagnon_distribution": rapport}})
    except Exception as err:                                   # noqa: BLE001
        return {"etapes": ["8h00 distribuer : ÉCHEC"], "erreurs": [str(err)]}


async def cloturer_run(etat: EtatRun, client) -> dict:
    """RÉGISSEUR (18h00) : clôture — statut « cloture » ou « echec »."""
    statut = "echec" if etat.get("erreurs") else "cloture"
    mise = _trace(etat, "cloturer_run", f"run_logs = {statut}")
    mise["statut"] = statut
    await client.ecrire("run_logs", [{
        "run_id": etat["run_id"],
        "type": etat["mode"],
        "statut": statut,
    }], si_doublon="mettre_a_jour")
    return mise


def nouveau_run_id(mode: str, date: str) -> str:
    """run-<date>-<mode>[-<suffixe>] — unique (clé run_logs)."""
    return f"run-{date}-{mode}-{uuid.uuid4().hex[:6]}"
