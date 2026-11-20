# ═══════════════════════════════════════════════════════════════════
# Tests de sécurité du MCP base-donnees — SANS base de données.
# On teste la couche de validation (securite.py) directement.
# ═══════════════════════════════════════════════════════════════════
import pytest

from securite import (
    TABLES,
    ErreurAcces,
    valider_appelant,
    valider_colonnes,
    valider_limite,
    valider_table,
)

# ── Appelants ──────────────────────────────────────────────────────
def test_appelant_inconnu_rejete():
    with pytest.raises(ErreurAcces):
        valider_appelant("hacker")


def test_les_sept_appelants_connus():
    for appelant in ("RÉGISSEUR", "INSPECTEUR", "COMPAGNON", "JUGE",
                     "CONCIERGE", "SENTINELLE", "backend"):
        assert valider_appelant(appelant)


# ── Tables : ce qui n'est pas listé = interdit ─────────────────────
def test_table_inconnue_rejetee():
    with pytest.raises(ErreurAcces):
        valider_table("auth.users", "backend", "lit")


def test_16_tables_presentes():
    assert len(TABLES) == 16


def test_hors_perimetre_rejete_inspecteur():
    # INSPECTEUR ne peut PAS lire les scores (matrice v3.1)
    with pytest.raises(ErreurAcces):
        valider_table("scores", "INSPECTEUR", "lit")


def test_hors_perimetre_rejete_regisseur():
    # RÉGISSEUR ne touche aucune donnée métier
    for table in ("tenders", "scores", "verdicts"):
        with pytest.raises(ErreurAcces):
            valider_table(table, "RÉGISSEUR", "lit")
    assert valider_table("run_logs", "RÉGISSEUR", "ecrit")


def test_concierge_lit_scores_mode_client():
    # La matrice v3.1 autorise CONCIERGE à lire scores/verdicts (mode client,
    # RLS company_id) — jamais en mode visiteur (garanti côté agent).
    assert {"scores", "verdicts"} <= valider_appelant("CONCIERGE")["lit"]


def test_ecriture_hors_perimetre_rejetee():
    with pytest.raises(ErreurAcces):
        valider_table("entreprises", "COMPAGNON", "ecrit")


def test_backend_tout_perimetre():
    perim = valider_appelant("backend")
    assert perim["lit"] == perim["ecrit"] == set(TABLES)


# ── Colonnes : liste blanche stricte ───────────────────────────────
def test_colonne_inconnue_rejetee():
    with pytest.raises(ErreurAcces):
        valider_colonnes("tenders", {"montant; DROP TABLE tenders"}, "filtre")


def test_colonnes_tenders_conformes_schema():
    defs = valider_colonnes(
        "tenders", {"reference", "organisme", "montant_mad", "date_collecte",
                    "source", "statut"}, "filtre"
    )
    assert "reference" in defs


def test_colonne_plateforme_utilisateurs():
    defs = valider_colonnes("utilisateurs", {"company_id", "nom", "email", "role"}, "filtre")
    assert "email" in defs


# ── Limites de lecture (batch plafonné) ────────────────────────────
def test_limite_plafonnee_a_1000():
    assert valider_limite(5000) == 1000
    assert valider_limite(500) == 500


def test_limite_invalide_rejetee():
    with pytest.raises(ErreurAcces):
        valider_limite(0)
