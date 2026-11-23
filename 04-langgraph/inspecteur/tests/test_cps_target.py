from __future__ import annotations

from datetime import date

from inspecteur import cps_target

TODAY = date(2026, 11, 20)


def test_normalisation():
    assert cps_target.normalize_sector("Travaux & BTP") == "travaux"
    assert cps_target.normalize_sector("construction") == "travaux"
    assert cps_target.normalize_sector("Informatique") == "informatique"
    assert cps_target.normalize_region("Casablanca") == "casa-settat"
    assert cps_target.normalize_region("Tanger") == "tanger-tetouan-alhoceima"


def test_envelope_depuis_profils():
    env = cps_target.build_envelope([
        {"secteur": "construction", "region": "casa-settat", "capacite_mad": 3_000_000},
        {"secteur": "it", "region": "tanger", "capacite_mad": 8_000_000},
    ])
    assert {"travaux", "informatique"} <= env["sectors"]
    assert {"casa-settat", "tanger-tetouan-alhoceima"} <= env["regions"]
    assert env["max_capacity"] == 8_000_000
    assert env["profile_count"] == 2


def test_envelope_repli_sans_profil():
    env = cps_target.build_envelope([])
    assert "travaux" in env["sectors"]
    assert env["regions"] == set()
    assert env["max_capacity"] == 8_000_000


def test_pertinence():
    env = cps_target.build_envelope([
        {"secteur": "construction", "region": "casa-settat", "capacite_mad": 3_000_000},
    ])
    base = {"statut": "ouvert", "date_remise": "2026-12-01",
            "secteur": "construction", "region": "Casablanca", "montant_mad": 1_500_000}

    assert cps_target.is_pertinent(base, env, today=TODAY)["ok"] is True

    check = cps_target.is_pertinent({**base, "statut": "clos"}, env, today=TODAY)
    assert check == {"ok": False, "reason": "statut_clos"}

    check = cps_target.is_pertinent({**base, "date_remise": "2026-11-01"}, env, today=TODAY)
    assert check["reason"] == "echeance_depassee"

    check = cps_target.is_pertinent({**base, "secteur": "informatique"}, env, today=TODAY)
    assert check["reason"] == "secteur_hors_cible"

    check = cps_target.is_pertinent({**base, "region": "Tanger"}, env, today=TODAY)
    assert check["reason"] == "region_hors_cible"

    check = cps_target.is_pertinent({**base, "montant_mad": 50_000_000}, env, today=TODAY)
    assert check["reason"] == "montant_au_dessus_capacite"

    # montant inconnu : on ne rejette pas
    assert cps_target.is_pertinent({**base, "montant_mad": None}, env, today=TODAY)["ok"] is True

    # secteur non renseigné par le portail : on ne rejette pas par excès
    assert cps_target.is_pertinent({**base, "secteur": "autre"}, env, today=TODAY)["ok"] is True
