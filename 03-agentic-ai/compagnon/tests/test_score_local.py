import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import score_local  # noqa: E402


COMPAGNIE = {
    "company_id": "EXPLEO-IT-001",
    "secteur": "it",
    "region": "casa-settat",
    "capacite_mad": 2_000_000,
    "qualifications": ["Q1"],
    "historique": [],
}

TENDER = {
    "reference": "TEST/1",
    "secteur": "informatique",
    "region": "casa-settat",
    "montant_mad": 1_000_000,
    "caution_mad": 50_000,
    "delai_jours": 90,
    "qualifications_exigees": ["Q1"],
}


def test_score_is_capped_without_documentary_evidence():
    resultat = score_local.score(dict(TENDER), COMPAGNIE)
    assert resultat["match_total"] <= 72
    assert resultat["composantes"]["confiance"] in ("moyen", "faible")


def test_score_is_capped_at_65_when_no_amount_and_no_evidence():
    tender = dict(TENDER, montant_mad=0, caution_mad=0, extraction={})
    resultat = score_local.score(tender, COMPAGNIE)
    assert resultat["match_total"] <= 65
    assert resultat["composantes"]["confiance"] == "faible"


def test_full_evidence_allows_high_match():
    tender = dict(TENDER, extraction={
        "caution_mad": 50_000,
        "budget_mad": 1_000_000,
        "signals": ["caution", "budget"],
        "quality": "riche",
    })
    resultat = score_local.score(tender, COMPAGNIE)
    assert resultat["match_total"] > 72
    assert resultat["composantes"]["confiance"] == "eleve"
