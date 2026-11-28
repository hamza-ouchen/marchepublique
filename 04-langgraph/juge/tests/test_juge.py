import copy
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import juge  # noqa: E402
import db_juge  # noqa: E402


TENDER = {
    "reference": "TEST/1",
    "objet": "Test",
    "montant_mad": 1_000_000,
    "caution_mad": 50_000,
    "delai_jours": 90,
    "qualifications_exigees": ["Q1"],
    "extraction": {"caution_mad": 50_000, "budget_mad": 1_000_000,
                   "signals": ["caution", "budget"], "quality": "riche"},
}
ENTREPRISE = {"company_id": "EXPLEO-IT-001", "capacite_mad": 5_000_000,
              "qualifications": ["Q1"]}
ABSENT = object()


def _tender(**champs):
    tender = copy.deepcopy(TENDER)
    for cle, valeur in champs.items():
        if valeur is ABSENT:
            if cle in tender:
                del tender[cle]
        elif cle == "extraction":
            extraction = copy.deepcopy(TENDER["extraction"])
            for sous_cle, sous_valeur in valeur.items():
                if sous_valeur is ABSENT:
                    extraction.pop(sous_cle, None)
                else:
                    extraction[sous_cle] = sous_valeur
            tender["extraction"] = extraction
        else:
            tender[cle] = valeur
    return tender


def _installer(monkeypatch, score_total, confiance, has_doc, *, tender=None,
               entreprise=None, section=None):
    ecrits = []
    monkeypatch.setattr(db_juge, "scores_for_date", lambda *a: [{
        "company_id": "EXPLEO-IT-001", "reference": "TEST/1",
        "match_total": score_total,
        "composantes": {"confiance": confiance},
    }])
    monkeypatch.setattr(db_juge, "doc_index", lambda: {
        "TEST/1": {"has_doc": has_doc, "nb_documents": 1 if has_doc else 0,
                   "nb_sections": 1}
    })
    monkeypatch.setattr(db_juge, "tender_by_reference",
                        lambda ref: copy.deepcopy(tender or TENDER))
    monkeypatch.setattr(db_juge, "entreprise_by_id",
                        lambda cid: copy.deepcopy(entreprise or ENTREPRISE))
    monkeypatch.setattr(db_juge, "qualification_section",
                        lambda ref: copy.deepcopy(section) if section else None)
    monkeypatch.setattr(db_juge, "upsert_verdict", lambda payload: ecrits.append(payload))
    monkeypatch.setattr(db_juge, "commit_verdicts", lambda: None)
    return ecrits


def test_score_below_45_is_no_go(monkeypatch):
    ecrits = _installer(monkeypatch, 40, "eleve", True)
    rapport = juge.juger("2026-11-23", "EXPLEO-IT-001")
    assert rapport["no_go"] == 1
    assert ecrits[0]["verdict"] == "NO_GO"


def test_go_requires_score_75_and_high_confidence(monkeypatch):
    ecrits = _installer(monkeypatch, 80, "faible", True)
    rapport = juge.juger("2026-11-23", "EXPLEO-IT-001")
    assert rapport["a_etudier"] == 1
    assert ecrits[0]["verdict"] == "A_ETUDIER"
    assert ecrits[0]["controles"]["_confiance"] == "faible"


def test_go_when_all_controls_are_green(monkeypatch):
    ecrits = _installer(monkeypatch, 85, "eleve", True)
    rapport = juge.juger("2026-11-23", "EXPLEO-IT-001")
    assert rapport["go"] == 1
    assert ecrits[0]["verdict"] == "GO"


@pytest.mark.parametrize("valeur", [0, None, ABSENT])
def test_caution_inconnue_bloque_le_go(monkeypatch, valeur):
    tender = _tender(caution_mad=valeur,
                     extraction={"caution_mad": valeur})
    ecrits = _installer(monkeypatch, 95, "eleve", True, tender=tender)
    rapport = juge.juger("2026-11-23", "EXPLEO-IT-001")
    assert rapport["a_etudier"] == 1
    assert rapport["go"] == 0
    controles = ecrits[0]["controles"]
    assert controles["caution_vs_capacite"] == "inconnu"
    assert any("caution" in j["constat"].lower() for j in ecrits[0]["justifications"])
    assert any("caution" in r.lower() for r in ecrits[0]["risques_a_verifier"])
    assert len(ecrits[0]["risques_a_verifier"]) >= 3


@pytest.mark.parametrize("valeur", [0, None, ABSENT])
def test_montant_inconnu_bloque_le_go(monkeypatch, valeur):
    tender = _tender(montant_mad=valeur,
                     extraction={"budget_mad": valeur})
    ecrits = _installer(monkeypatch, 95, "eleve", True, tender=tender)
    rapport = juge.juger("2026-11-23", "EXPLEO-IT-001")
    assert rapport["a_etudier"] == 1
    assert rapport["go"] == 0
    assert ecrits[0]["controles"]["ice_attestations"] == "inconnu"
    assert any("montant" in j["constat"].lower() or "attestation" in j["constat"].lower()
               for j in ecrits[0]["justifications"])
    assert any("montant" in r.lower() for r in ecrits[0]["risques_a_verifier"])
    assert len(ecrits[0]["risques_a_verifier"]) >= 3


@pytest.mark.parametrize("valeur", [None, [], ABSENT])
def test_qualifications_inconnues_bloquent_le_go(monkeypatch, valeur):
    tender = _tender(qualifications_exigees=valeur)
    ecrits = _installer(monkeypatch, 95, "eleve", True, tender=tender)
    rapport = juge.juger("2026-11-23", "EXPLEO-IT-001")
    assert rapport["a_etudier"] == 1
    assert rapport["go"] == 0
    assert ecrits[0]["controles"]["qualifications"] == "inconnu"
    assert any("qualification" in j["constat"].lower()
               for j in ecrits[0]["justifications"])
    assert any("qualification" in r.lower() for r in ecrits[0]["risques_a_verifier"])
    assert len(ecrits[0]["risques_a_verifier"]) >= 3


@pytest.mark.parametrize("valeur", [0, None, ABSENT])
def test_delai_inconnu_bloque_le_go(monkeypatch, valeur):
    tender = _tender(delai_jours=valeur)
    ecrits = _installer(monkeypatch, 95, "eleve", True, tender=tender)
    rapport = juge.juger("2026-11-23", "EXPLEO-IT-001")
    assert rapport["a_etudier"] == 1
    assert rapport["go"] == 0
    assert ecrits[0]["controles"]["delai_atteignable"] == "inconnu"
    assert any("délai" in j["constat"].lower() for j in ecrits[0]["justifications"])
    assert any("délai" in r.lower() for r in ecrits[0]["risques_a_verifier"])
    assert len(ecrits[0]["risques_a_verifier"]) >= 3


def test_zero_extrait_nest_pas_une_preuve_de_confiance(monkeypatch):
    tender = _tender(caution_mad=0, montant_mad=0,
                     extraction={"caution_mad": "0", "budget_mad": "0"})
    ecrits = _installer(monkeypatch, 95, None, True, tender=tender)
    juge.juger("2026-11-23", "EXPLEO-IT-001")
    assert ecrits[0]["controles"]["_confiance"] == "faible"
