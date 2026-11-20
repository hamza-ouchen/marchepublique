"""Tests unitaires basiques pour securite.py (à lancer avec pytest)."""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

import securite
from securite import (
    SecuriteError,
    marquer_envoi,
    marquer_ref_traite,
    verifier_appelant,
    verifier_destinataire,
    verifier_gabarit,
    verifier_idempotence,
    verifier_rate_limit,
)


def test_gabarit_inconnu_rejete():
    with pytest.raises(SecuriteError):
        verifier_gabarit("ce_gabarit_n_existe_pas", {})


def test_gabarit_variables_manquantes_rejete():
    with pytest.raises(SecuriteError):
        verifier_gabarit("digest", {"nom_client": "Ahmed"})  # variables manquantes


def test_gabarit_variables_completes_ok():
    verifier_gabarit(
        "digest",
        {"nom_client": "Ahmed", "nb_appels_offres": "3", "lien_dashboard": "https://..."},
    )  # ne doit pas lever d'exception


def test_idempotence_rejette_doublon():
    verifier_idempotence("ref-test-001")  # 1ère vérification : OK (pas encore traité)
    marquer_ref_traite("ref-test-001")    # simule un envoi réussi
    with pytest.raises(SecuriteError):
        verifier_idempotence("ref-test-001")  # 2e vérification avec même ref : rejeté


def test_appelant_autorise_ok():
    verifier_appelant("digest", "COMPAGNON")  # ne doit pas lever d'exception


def test_appelant_non_autorise_rejete():
    with pytest.raises(SecuriteError):
        verifier_appelant("digest", "CONCIERGE")  # digest = COMPAGNON uniquement


def test_appelant_inconnu_rejete():
    with pytest.raises(SecuriteError):
        verifier_appelant("alerte_hitl", "INSPECTEUR")  # agent hors whitelist


# --- Format du destinataire (E.164 / email) --------------------------------

@pytest.mark.parametrize(
    "numero",
    ["212612345678", "+212612345678", "33612345678"],
)
def test_destinataire_whatsapp_e164_valide_ok(numero):
    verifier_destinataire("whatsapp", numero)  # ne doit pas lever d'exception


@pytest.mark.parametrize(
    "numero",
    [
        "0612345678",        # 0 initial après "+" absent -> pas E.164
        "0021261234567",     # double indicatif / format local marocain
        "abc123",            # pas un numéro
        "123",                # trop court
        "",                   # vide
    ],
)
def test_destinataire_whatsapp_invalide_rejete(numero):
    with pytest.raises(SecuriteError):
        verifier_destinataire("whatsapp", numero)


@pytest.mark.parametrize("email", ["ahmed@example.com", "a.b+c@sous.domaine.ma"])
def test_destinataire_email_valide_ok(email):
    verifier_destinataire("email", email)  # ne doit pas lever d'exception


@pytest.mark.parametrize("email", ["pas-un-email", "ahmed@", "@example.com", ""])
def test_destinataire_email_invalide_rejete(email):
    with pytest.raises(SecuriteError):
        verifier_destinataire("email", email)


def test_destinataire_canal_inconnu_rejete():
    with pytest.raises(SecuriteError):
        verifier_destinataire("sms", "212612345678")


# --- Rate limiting (burst + par conversation) -------------------------------

def test_rate_limit_2e_appel_rapide_rejete():
    """Le brief limite 1 message / 5 min par destinataire : le 2e appel
    immédiat (même conversation) doit être rejeté, quel que soit le
    seuil de burst configuré."""
    destinataire = "212600000001"
    verifier_rate_limit(destinataire)  # 1er appel : OK
    marquer_envoi(destinataire)
    with pytest.raises(SecuriteError, match="Trop tôt"):
        verifier_rate_limit(destinataire)  # 2e appel immédiat : rejeté


def test_rate_limit_burst_depasse_rejete(monkeypatch):
    """Vérifie que le seuil RATE_LIMIT_BURST_MAX est bien appliqué :
    si >= burst_max appels sont déjà enregistrés dans la dernière minute
    pour ce destinataire, le prochain appel est rejeté pour cause de
    burst (et non pour la règle 'par conversation')."""
    monkeypatch.setenv("RATE_LIMIT_BURST_MAX", "3")
    destinataire = "212600000099"

    # Injection directe de l'état interne pour isoler le contrôle burst
    # de la règle "1 message / 5 min" (qui rejetterait de toute façon
    # dès le 2e appel réel — voir le test ci-dessous pour le cas réel).
    compteur = securite._COMPTEURS.setdefault(
        destinataire, securite._CompteurDestinataire()
    )
    maintenant = time.time()
    compteur.horodatages = [maintenant, maintenant, maintenant]  # 3 appels < 60s

    with pytest.raises(SecuriteError, match="Burst dépassé"):
        verifier_rate_limit(destinataire)


def test_rate_limit_burst_atteignable_si_limite_conversation_suffisante(monkeypatch):
    """BUGFIX : lecture numerique de RATE_LIMIT_PAR_CONVERSATION_5MIN.
    Le seuil de burst ne devient testable en conditions reelles que si
    cette limite est reglee a une valeur >= RATE_LIMIT_BURST_MAX (sinon
    elle bloque le 2e envoi avant que le burst ne soit jamais atteint)."""
    monkeypatch.setenv("RATE_LIMIT_PAR_CONVERSATION_5MIN", "5")
    monkeypatch.setenv("RATE_LIMIT_BURST_MAX", "3")
    monkeypatch.setenv("RATE_LIMIT_PAR_DESTINATAIRE_24H", "10")  # isole du test
    destinataire = "212600000077"

    verifier_rate_limit(destinataire)
    marquer_envoi(destinataire)
    verifier_rate_limit(destinataire)
    marquer_envoi(destinataire)
    verifier_rate_limit(destinataire)
    marquer_envoi(destinataire)

    with pytest.raises(SecuriteError, match="Burst dépassé"):
        verifier_rate_limit(destinataire)  # 4e appel réel : burst atteint
