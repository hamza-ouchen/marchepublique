# ═══════════════════════════════════════════════════════════════════
# Tests du graphe RÉGISSEUR — zéro réseau, zéro base, zéro LLM.
# Le client MCP est remplacé par un double (en mémoire) ; les agents
# répondent en mode demo (rapports simulés de noeuds.py).
# ═══════════════════════════════════════════════════════════════════
import asyncio

import pytest

from client_mcp import ClientMCPRegisseur
from etat_run import nouvel_etat
from graphe import construire_graphe
from noeuds import nouveau_run_id


@pytest.fixture()
def client_memoire():
    return ClientMCPRegisseur()      # sans DATABASE_URL → mode mémoire


def lancer(client, mode="cron", date="2026-11-17", demo=True):
    etat = nouvel_etat(mode, date, demo, nouveau_run_id(mode, date))
    app = construire_graphe(client)
    return asyncio.run(app.ainvoke(etat))


def test_chaine_complete_cron(client_memoire):
    etat = lancer(client_memoire)
    assert etat["statut"] == "cloture"
    assert etat["erreurs"] == []
    noms = [e.split()[1] for e in etat["etapes"]]
    # L'ordre exact de la chaîne du matin (CAS A) :
    assert noms == ["ouvrir_run", "collecter", "collecter_documents",
                    "calculer_scores", "statuer", "composer_digest",
                    "distribuer", "cloturer_run"]
    # Les horaires sont ceux de la matrice :
    assert etat["etapes"][0].startswith("6h00")
    assert etat["etapes"][4].startswith("7h00")
    assert etat["etapes"][7].startswith("18h00")


def test_run_ouvert_puis_cloture(client_memoire):
    etat = lancer(client_memoire)
    runs = client_memoire.memoire["run_logs"]
    assert len(runs) == 3      # ouvert + maj collecte + clôture (upsert)
    assert runs[0]["statut"] == "ouvert"
    assert runs[-1]["statut"] == "cloture"


def test_mode_backfill_traverse_toute_la_chaine(client_memoire):
    etat = lancer(client_memoire, mode="backfill")
    assert etat["statut"] == "cloture"
    assert etat["mode"] == "backfill"
    assert etat["rapport"]["inspecteur"]["source"] == "backfill-demo"


def test_echec_inspecteur_saute_le_reste(client_memoire, monkeypatch):
    import noeuds

    async def crash(_etat):
        raise RuntimeError("portail en panne")

    monkeypatch.setattr(noeuds, "APPEL_INSPECTEUR", crash)
    etat = lancer(client_memoire)
    # Le run est marqué « echec » — jamais à moitié fait en silence :
    assert etat["statut"] == "echec"
    assert any("portail en panne" in e for e in etat["erreurs"])
    # Les étapes suivantes sont sautées (garde-fou) :
    noms = [e.split()[1] for e in etat["etapes"] if "SAUTÉ" in e]
    assert set(noms) == {"calculer_scores", "collecter_documents", "statuer",
                         "composer_digest", "distribuer"}
    runs = client_memoire.memoire["run_logs"]
    assert runs[-1]["statut"] == "echec"


def test_echec_documentaire_bloque_le_scoring(client_memoire, monkeypatch):
    import noeuds

    async def unavailable(_etat):
        raise RuntimeError("stockage indisponible")

    monkeypatch.setattr(noeuds, "APPEL_INSPECTEUR_DOCUMENTS", unavailable)
    etat = lancer(client_memoire)
    assert etat["statut"] == "echec"
    assert any("calculer_scores : SAUTÉ" in e for e in etat["etapes"])


def test_regisseur_n_ecrit_que_run_logs(client_memoire):
    """Le RÉGISSEUR ne touche aucune donnée métier (matrice v3.1)."""
    lancer(client_memoire)
    assert set(client_memoire.memoire) == {"run_logs"}
