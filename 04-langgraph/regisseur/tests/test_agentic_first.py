# Tests des workflows historiques et de leur isolation dans le RÉGISSEUR.
# Zéro réseau : les deux clients sont simulés.
import asyncio
import json

import noeuds


ETAT = {
    "date": "2026-11-26",
    "company_id": "EXPLEO-IT-001",
    "demo": False,
    "mode": "cron",
    "collecte": "incremental",
}


def _activer(monkeypatch):
    monkeypatch.setattr(noeuds, "_agentic_d_abord", lambda: True)
    monkeypatch.setattr(noeuds, "_agentic_timeout", lambda: 2)


def test_scores_agentic_utilises_sans_appel_a2a(monkeypatch):
    _activer(monkeypatch)
    monkeypatch.setattr(
        noeuds.agentic_flow,
        "run_compagnon",
        lambda *args: (True, '{"scores_ecrits": 7, "scores_calcules": 7, '
                             '"tenders_lus": 7, "algo_version": "flow"}'),
    )

    def interdit(*_args, **_kwargs):
        raise AssertionError("A2A ne doit pas être appelé après un succès Agentic")

    monkeypatch.setattr(noeuds, "appeler_a2a", interdit)
    rapport = asyncio.run(noeuds._appel_compagnon_scores_agentic_legacy(dict(ETAT)))
    assert rapport["scores_ecrits"] == 7
    assert rapport["source"] == "flow_compagnon"


def test_scores_timeout_basculle_sur_langgraph(monkeypatch):
    _activer(monkeypatch)

    def timeout(*_args):
        raise TimeoutError("flow timeout")

    monkeypatch.setattr(noeuds.agentic_flow, "run_compagnon", timeout)
    monkeypatch.setattr(
        noeuds,
        "appeler_a2a",
        lambda *args, **kwargs: asyncio.sleep(
            0, result={"scores_ecrits": 5, "source": "score_local"}
        ),
    )
    rapport = asyncio.run(noeuds._appel_compagnon_scores_agentic_legacy(dict(ETAT)))
    assert rapport["scores_ecrits"] == 5
    assert rapport["source"] == "langgraph_a2a_fallback"
    assert "TimeoutError" in rapport["detail_agentic"]


def test_scores_agentic_idempotents_sont_utilises_sans_a2a(monkeypatch):
    _activer(monkeypatch)
    monkeypatch.setattr(
        noeuds.agentic_flow,
        "run_compagnon",
        lambda *args: (True, '{"scores_ecrits": 0, "scores_calcules": 177, '
                             '"tenders_lus": 2296, "source": "flow_compagnon"}'),
    )

    def interdit(*_args, **_kwargs):
        raise AssertionError("A2A ne doit pas être appelé après un run idempotent")

    monkeypatch.setattr(noeuds, "appeler_a2a", interdit)
    rapport = asyncio.run(noeuds._appel_compagnon_scores_agentic_legacy(dict(ETAT)))
    assert rapport["scores_calcules"] == 177
    assert rapport["source"] == "flow_compagnon"


def test_scores_partiels_basculle_sur_langgraph(monkeypatch):
    _activer(monkeypatch)
    monkeypatch.setattr(
        noeuds.agentic_flow,
        "run_compagnon",
        lambda *args: (True, '{"scores_ecrits": 3, "scores_calcules": 3, '
                             '"tenders_lus": 10, "partiel": true}'),
    )
    monkeypatch.setattr(
        noeuds,
        "appeler_a2a",
        lambda *args, **kwargs: asyncio.sleep(
            0, result={"scores_ecrits": 10, "tenders_lus": 10}
        ),
    )
    rapport = asyncio.run(noeuds._appel_compagnon_scores_agentic_legacy(dict(ETAT)))
    assert rapport["scores_ecrits"] == 10
    assert rapport["source"] == "langgraph_a2a_fallback"


def test_juge_revue_agentic_puis_verdicts_langgraph(monkeypatch):
    _activer(monkeypatch)
    monkeypatch.setattr(
        noeuds.agentic_flow,
        "run_juge_flow",
        lambda *args: (True, '{"status":"blocked","publication_authorized":false}'),
    )
    monkeypatch.setattr(
        noeuds,
        "appeler_a2a",
        lambda *args, **kwargs: asyncio.sleep(
            0, result={"verdicts_ecrits": 12, "go": 4}
        ),
    )
    rapport = asyncio.run(noeuds._appel_juge_agentic_legacy(dict(ETAT)))
    assert rapport["verdicts_ecrits"] == 12
    assert rapport["source"] == "langgraph_a2a_fallback"
    assert "publication_authorized" in rapport["revision_agentic"]


def test_juge_agentic_avec_verdicts_valides_ne_passe_pas_en_a2a(monkeypatch):
    _activer(monkeypatch)
    verdict = {
        "reference": "TEST/1",
        "verdict": "A_ETUDIER",
        "controles": {cle: "inconnu" for cle in noeuds._CLES_CONTROLE},
        "justifications": [{"constat": "caution non vérifiée", "reference": "avis officiel"}],
        "risques_a_verifier": ["caution", "qualifications", "délai"],
    }
    monkeypatch.setattr(
        noeuds.agentic_flow,
        "run_juge_flow",
        lambda *args: (True, json.dumps({"verdicts_ecrits": 1, "go": 0,
                                         "verdicts": [verdict]})),
    )

    def interdit(*_args, **_kwargs):
        raise AssertionError("A2A ne doit pas être appelé après un succès Agentic")

    monkeypatch.setattr(noeuds, "appeler_a2a", interdit)
    rapport = asyncio.run(noeuds._appel_juge_agentic_legacy(dict(ETAT)))
    assert rapport["verdicts_ecrits"] == 1
    assert rapport["source"] == "flow_juge"


def test_juge_agentic_avec_verdicts_invalides_basculle_sur_langgraph(monkeypatch):
    _activer(monkeypatch)
    monkeypatch.setattr(
        noeuds.agentic_flow,
        "run_juge_flow",
        lambda *args: (True, '{"verdicts_ecrits": 9, "go": 3, '
                             '"verdicts": [{"verdict": "GO"}]}'),
    )
    monkeypatch.setattr(
        noeuds,
        "appeler_a2a",
        lambda *args, **kwargs: asyncio.sleep(
            0, result={"verdicts_ecrits": 12, "source": "juge_local"}
        ),
    )
    rapport = asyncio.run(noeuds._appel_juge_agentic_legacy(dict(ETAT)))
    assert rapport["verdicts_ecrits"] == 12
    assert rapport["source"] == "langgraph_a2a_fallback"
    assert "verdicts_ecrits" in rapport["revision_agentic"]


def test_entrees_actives_utilisent_uniquement_a2a(monkeypatch):
    monkeypatch.setenv("SOU9NA_AGENTIC_FIRST", "1")
    appels = []

    def interdit(*_args):
        raise AssertionError("Un workflow Agentic a été appelé")

    async def a2a(skill, donnees):
        appels.append((skill, donnees))
        return {"source": skill}

    monkeypatch.setattr(noeuds, "_agentic_d_abord", interdit)
    monkeypatch.setattr(noeuds, "appeler_a2a", a2a)
    assert asyncio.run(noeuds.APPEL_COMPAGNON_SCORES(dict(ETAT))) == {
        "source": "calculer_match",
    }
    assert asyncio.run(noeuds.APPEL_JUGE(dict(ETAT))) == {"source": "statuer"}
    assert [skill for skill, _ in appels] == ["calculer_match", "statuer"]
    assert appels[1][1]["seuil"] == 75
