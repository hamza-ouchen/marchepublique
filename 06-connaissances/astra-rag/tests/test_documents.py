"""Régressions d'extraction, couverture documentaire et découpage."""

import pytest

from sou9na_rag.documents import DocumentError, clean_page, make_chunks, split_text


def sample(pages=None):
    """Fournit un corpus entièrement fictif avec question traversant deux pages."""
    return {
        "document": "test.pdf",
        "document_sha256": "a" * 64,
        "page_count": 3,
        "pages": pages
        or [
            "00.Synthese\nTableau : information importante.\n"
            "[Q-001] Premiere question ?\nDebut de reponse",
            "suite de la reponse.\nCatégorie : Produit · Mots-clés : exemple · Source : Test\n"
            "[Q-002] Deuxieme question ?\nAutre reponse.\n"
            "Catégorie : Regle · Mots-clés : exemple · Source : Document de test",
            "06.Glossaire\nCPS : document contractuel.\nمرحبا سوقنا",
        ],
    }


def test_preserves_normal_words_and_arabic():
    """Le nettoyage ne soude pas les mots courts et conserve l'arabe."""
    assert clean_page("Il y a un an\nمرحبا سوقنا\x00") == "Il y a un an\nمرحبا سوقنا"


def test_coverage_pages_and_sources():
    """Une question multipage, les synthèses et le glossaire restent citables."""
    chunks = make_chunks(sample(), expected_questions=2)
    qa = [chunk for chunk in chunks if chunk["block_id"] == "Q-001"][0]
    assert (qa["page_start"], qa["page_end"]) == (1, 2)
    assert "suite de la reponse" in qa["text"]
    assert qa["declared_source"] == "Test"
    assert qa["legal_validation"] == "not_verified"
    assert {c["content_type"] for c in chunks} == {"summary", "qa", "glossary"}
    assert "مرحبا سوقنا" in chunks[-1]["text"]


@pytest.mark.parametrize("bad_id", ["Q-001", "Q-003"])
def test_rejects_duplicate_or_missing_questions(bad_id):
    """Un corpus incomplet n'est pas publié."""
    document = sample()
    document["pages"][1] = document["pages"][1].replace("Q-002", bad_id)
    with pytest.raises(DocumentError):
        make_chunks(document, expected_questions=2)


def test_chunk_ids_are_stable_and_versions_separate():
    """Une même version produit les mêmes identifiants ; un autre PDF est séparé."""
    first = make_chunks(sample(), expected_questions=2)
    assert first == make_chunks(sample(), expected_questions=2)
    other = sample()
    other["document_sha256"] = "b" * 64
    second = make_chunks(other, expected_questions=2)
    assert not {c["_id"] for c in first} & {c["_id"] for c in second}


def test_long_text_has_no_silent_tail_loss():
    """Chaque mot distinct, notamment le dernier, reste présent après découpage."""
    text = " ".join(f"mot{i:05}" for i in range(1500))
    pieces = split_text(text)
    covered = set(" ".join(pieces).split())
    assert set(text.split()) <= covered
    assert all(0 < len(piece) <= 1800 for piece in pieces)


def test_empty_cleaned_text_does_not_create_empty_chunks():
    """Le cas de caractères nuls du code externe ne crée plus de passage vide."""
    assert clean_page("\x00" * 20) == ""
    assert split_text(clean_page("\x00" * 20)) == []
