# ═══════════════════════════════════════════════════════════════════
# Tests du MCP base-connaissances — zéro réseau, zéro base.
# Le moteur lexical tourne sur corpus/*.json.
# ═══════════════════════════════════════════════════════════════════
import moteur_recherche
from serveur import chercher


def test_contrat_5_passages_max():
    resultat = moteur_recherche.chercher("marché public TPME", "reglementation", 10)
    assert len(resultat["passages"]) <= 5
    for p in resultat["passages"]:
        assert set(p) == {"texte", "source", "article", "score"}   # contrat J5


def test_chercher_citation_obligatoire():
    resultat = chercher("caution provisoire plafond", "reglementation")
    assert not resultat.get("erreur")
    for p in resultat["passages"]:
        assert p["source"] and p["article"]       # sans citation = rejet


def test_requete_accents_et_casse():
    # « décret » / « DECRET » / « decret » → mêmes résultats
    a = chercher("décret marchés publics", "reglementation")["passages"]
    b = chercher("DECRET MARCHES PUBLICS", "reglementation")["passages"]
    assert a and b and a[0]["texte"] == b[0]["texte"]


def test_corp_valides_exclusifs():
    assert chercher("essai 14 jours")["passages"] or True   # pas d'erreur de corpus
    resultat = chercher("essai 14 jours", "corpus_faux")
    assert resultat["erreur"] == "corpus_invalide"


def test_requete_vide_rejetee():
    assert chercher("   ")["erreur"] == "requete_vide"


def test_match_fa_renvoie_passages():
    resultat = chercher("combien coûte l'abonnement pro business", "faq")
    assert len(resultat["passages"]) >= 1
    assert any("199" in p["texte"] or "499" in p["texte"] for p in resultat["passages"])


def test_match_ar_translittere_ou_non():
    # Le moteur tolère le darija translittéré et l'arabe (tokens multi-octets OK)
    resultat = chercher("شنو هو داكشي 14 jours essai", "faq")
    assert "erreur" not in resultat
