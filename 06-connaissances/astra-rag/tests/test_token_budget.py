"""Régression de la limite réelle 512 tokens du service d'embeddings."""

from sou9na_rag.token_budget import MAX_TOKENS, fit_budget, token_count


def test_long_multilingual_text_fits_without_losing_tail():
    """La fin de l'arabe, du français et des références n'est pas tronquée."""
    text = (
        "Caution provisoire, marchés publics, délais. مرحبا بكم في سوقنا. " * 50
        + "FIN_DOCUMENT_TEST"
    )
    parts = fit_budget(text)
    assert len(parts) > 1
    assert all(token_count(part) <= MAX_TOKENS for part in parts)
    assert set(text.split()) <= set(" ".join(parts).split())
    assert "FIN_DOCUMENT_TEST" in parts[-1]


def test_question_context_is_kept_after_split():
    """Les sous-passages restent rattachés à la question."""
    prefix = "[Q-001] Quelle caution ?"
    parts = fit_budget("Une reponse longue et detaillee. " * 100, prefix)
    assert all(part.startswith(prefix) for part in parts)
    assert all(token_count(part) <= MAX_TOKENS for part in parts)
