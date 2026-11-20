# ═══════════════════════════════════════════════════════════════════
# Tests du MCP portail-marches — mode demo, zéro réseau.
# ═══════════════════════════════════════════════════════════════════
from client_portail import rechercher, rechercher_avis_demo
from serveur import rechercher_avis


def test_demo_renvoie_3_pages():
    resultat = rechercher_avis_demo("2026-11-17")
    assert resultat["source"] == "demo"
    assert len(resultat["pages"]) == 3
    for page in resultat["pages"]:
        assert page["url"].startswith("fixture://avis/2026-11-17/")
        assert "AVIS" in page["contenu"]


def test_avis_fixtures_couvre_les_3_types():
    pages = rechercher_avis_demo("2026-11-17")["pages"]
    textes = " ".join(p["contenu"] for p in pages)
    assert "N°2026/DTR/0123" in textes      # ouvert (travaux)
    assert "N°2026/DTR/0124" in textes      # ouvert (informatique)
    assert "N°2026/DTR/0125" in textes      # attribution (archive P2)


def test_point_entree_mode_demo_explicite():
    resultat = rechercher("2026-11-18", mode="demo")
    assert resultat["source"] == "demo"


def test_date_invalide_rejetee():
    resultat = rechercher_avis("17/11/2026")
    assert resultat["erreur"] == "date_invalide"


def test_mode_invalide_rejete():
    resultat = rechercher_avis("2026-11-17", mode="intrus")
    assert resultat["erreur"] == "mode_invalide"
