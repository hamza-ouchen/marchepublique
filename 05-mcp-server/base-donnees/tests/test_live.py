# ═══════════════════════════════════════════════════════════════════
# Test « live » du MCP base-donnees — ne tourne QUE si DATABASE_URL
# est défini (sinon ignoré). Vérifie un cycle réel lire → ecrire.
# Usage (depuis le dossier base-donnees, avec la variable exportée) :
#   set DATABASE_URL=postgresql://...   (ou PowerShell : $env:DATABASE_URL="...")
#   python -m pytest tests/test_live.py -v
# ═══════════════════════════════════════════════════════════════════
import os

import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL"), reason="DATABASE_URL non défini"
)


def test_lire_tenders_comme_backend():
    from serveur import lire

    resultat = lire("tenders", appelant="backend", limite=5)
    assert resultat.get("nombre") == min(5, resultat.get("nombre", 0))
    assert "erreur" not in resultat


def test_cycle_run_logs_comme_regisseur():
    """Le RÉGISSEUR ouvre un run de test, le lit, puis l'upsert (clôture)."""
    from serveur import ecrire, lire

    run_id = "run-test-mcp-001"
    ouvert = ecrire(
        "run_logs",
        [{"run_id": run_id, "type": "manuel", "statut": "ouvert"}],
        appelant="RÉGISSEUR",
        si_doublon="mettre_a_jour",
    )
    assert ouvert["ecrites"] in (0, 1)          # 0 si le run existait déjà (upsert)

    lus = lire("run_logs", appelant="RÉGISSEUR", filtres={"run_id": run_id})
    assert lus["nombre"] == 1 and lus["lignes"][0]["run_id"] == run_id


def test_rejet_hors_perimetre_en_live():
    from serveur import lire

    resultat = lire("scores", appelant="INSPECTEUR")
    assert resultat["erreur"] == "acces_refuse"
