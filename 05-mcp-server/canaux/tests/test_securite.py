"""Tests unitaires basiques pour securite.py (à lancer avec pytest)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from securite import SecuriteError, marquer_ref_traite, verifier_gabarit, verifier_idempotence


def test_gabarit_inconnu_rejete():
    with pytest.raises(SecuriteError):
        verifier_gabarit("ce_gabarit_n_existe_pas", {})


def test_gabarit_variables_manquantes_rejete():
    with pytest.raises(SecuriteError):
        verifier_gabarit("digest_quotidien", {"nom_client": "Ahmed"})  # variables manquantes


def test_gabarit_variables_completes_ok():
    verifier_gabarit(
        "digest_quotidien",
        {"nom_client": "Ahmed", "nb_appels_offres": "3", "lien_dashboard": "https://..."},
    )  # ne doit pas lever d'exception


def test_idempotence_rejette_doublon():
    verifier_idempotence("ref-test-001")  # 1ère vérification : OK (pas encore traité)
    marquer_ref_traite("ref-test-001")    # simule un envoi réussi
    with pytest.raises(SecuriteError):
        verifier_idempotence("ref-test-001")  # 2e vérification avec même ref : rejeté
