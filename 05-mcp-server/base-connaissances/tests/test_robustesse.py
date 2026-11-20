# ═══════════════════════════════════════════════════════════════════
# Robustesse du moteur — zéro réseau, zéro base.
# Couvre : corpus absent / illisible / vide, Astra vide ou en panne,
# bornes de `nombre`, citations obligatoires, pluriels et accents.
# ═══════════════════════════════════════════════════════════════════
import json

import pytest

import moteur_recherche
from moteur_recherche import chercher, corpus_valide


@pytest.fixture()
def sans_astra(monkeypatch):
    for cle in ("ASTRA_DB_API_ENDPOINT", "ASTRA_DB_API_TOKEN",
                "ASTRA_DB_COLLECTION", "ASTRA_DB_KEYSPACE"):
        monkeypatch.delenv(cle, raising=False)
    monkeypatch.setenv("MOTEUR", "auto")


def test_corpus_absent_renvoie_vide(monkeypatch, tmp_path, sans_astra):
    monkeypatch.setattr(moteur_recherche, "CORPUS_DIR", tmp_path)
    resultat = chercher("caution provisoire", "faq")
    assert resultat["vide"] is True
    assert resultat["passages"] == []
    assert "absent" in resultat["message"]
    assert "erreur" not in resultat


def test_corpus_illisible_renvoie_vide(monkeypatch, tmp_path, sans_astra):
    (tmp_path / "faq.json").write_text("{ ceci n'est pas du JSON", encoding="utf-8")
    monkeypatch.setattr(moteur_recherche, "CORPUS_DIR", tmp_path)
    resultat = chercher("abonnement", "faq")
    assert resultat["vide"] is True
    assert "illisible" in resultat["message"]


def test_corpus_vide_renvoie_vide(monkeypatch, tmp_path, sans_astra):
    (tmp_path / "faq.json").write_text('{"passages": []}', encoding="utf-8")
    monkeypatch.setattr(moteur_recherche, "CORPUS_DIR", tmp_path)
    resultat = chercher("abonnement", "faq")
    assert resultat["vide"] is True
    assert resultat["passages"] == []
    assert "vide" in resultat["message"].lower()


def test_cps_sans_astra_est_structure(sans_astra):
    resultat = chercher("caution provisoire", "cps:2026/DTR/0123")
    assert resultat["vide"] is True
    assert resultat["erreur"] == "astra_non_configure"
    assert "Astra" in resultat["message"]


def test_astra_vide_est_expliquee(monkeypatch, sans_astra):
    monkeypatch.setattr(moteur_recherche, "_astra_config",
                        lambda: {"endpoint": "x", "token": "y",
                                 "collection": "sou9na", "keyspace": "default_keyspace"})
    monkeypatch.setattr(moteur_recherche, "_astra_compter", lambda config: 0)

    resultat = chercher("caution provisoire", "cps:2026/DTR/0123")
    assert resultat["vide"] is True
    assert resultat["astra"]["documents"] == 0
    assert "vide" in resultat["message"]


def test_astra_avec_documents_classe_et_cite(monkeypatch, sans_astra):
    monkeypatch.setattr(moteur_recherche, "_astra_config",
                        lambda: {"endpoint": "x", "token": "y",
                                 "collection": "sou9na", "keyspace": "default_keyspace"})
    monkeypatch.setattr(moteur_recherche, "_astra_compter", lambda config: 2)
    monkeypatch.setattr(moteur_recherche, "_astra_lire", lambda config, corpus, limite=500: [
        {"reference": "2026/DTR/0123", "filename": "cps.pdf", "section_no": 4,
         "numero": "4.1", "titre": "Caution provisoire",
         "text": "La caution provisoire est fixée à 1,5 % du montant estimé."},
        {"reference": "2026/DTR/0123", "filename": "cps.pdf", "section_no": 5,
         "numero": "5", "titre": "Qualifications",
         "text": "Le conducteur de travaux justifie de cinq ans d'expérience."},
    ])
    resultat = chercher("caution provisoire", "cps:2026/DTR/0123")
    assert resultat["vide"] is False
    premier = resultat["passages"][0]
    assert set(premier) == {"texte", "source", "article", "score"}
    assert premier["article"] == "4.1"
    assert "1,5 %" in premier["texte"]


def test_astra_en_panne_ne_leve_pas(monkeypatch, sans_astra):
    monkeypatch.setattr(moteur_recherche, "_astra_config",
                        lambda: {"endpoint": "x", "token": "y",
                                 "collection": "sou9na", "keyspace": "default_keyspace"})

    def panne(config):
        raise RuntimeError("timeout")

    monkeypatch.setattr(moteur_recherche, "_astra_compter", panne)
    resultat = chercher("caution", "cps:2026/DTR/0123")
    assert resultat["erreur"] == "astra_indisponible"
    assert resultat["vide"] is True


def test_nombre_est_borne():
    resultat = chercher("marché public", "reglementation", 50)
    assert 0 < len(resultat["passages"]) <= 5
    resultat_un = chercher("marché public", "reglementation", 0)
    assert len(resultat_un["passages"]) == 1


def test_pluriel_et_accents():
    resultat = chercher("cautions provisoires plafonnees", "reglementation")
    assert resultat["passages"]
    assert any("art. 24" in p["article"] for p in resultat["passages"])


def test_passage_sans_citation_est_ecarte():
    passages = [{"texte": "La caution est plafonnée.", "source": "décret"}]
    trouves, ignores = moteur_recherche._classer("caution", passages, 5)
    assert trouves == []
    assert ignores == 1


def test_corpus_cps_valide():
    assert corpus_valide("cps:2026/DTR/0123")
    assert not corpus_valide("cps:")
    assert not corpus_valide("corpus_faux")


def test_json_corpus_liste_accepte(monkeypatch, tmp_path, sans_astra):
    (tmp_path / "faq.json").write_text(json.dumps([
        {"texte": "L'essai dure 14 jours.", "source": "FAQ", "article": "essai"}
    ]), encoding="utf-8")
    monkeypatch.setattr(moteur_recherche, "CORPUS_DIR", tmp_path)
    resultat = chercher("essai 14 jours", "faq")
    assert resultat["vide"] is False
    assert resultat["passages"][0]["article"] == "essai"
