"""Raccordement MCP au package RAG, sans réseau ni secrets."""

from pathlib import Path

import moteur_recherche


def test_rag_mode_delegates_exact_corpus_and_count(monkeypatch):
    root = Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(root / "06-connaissances/astra-rag"))
    from sou9na_rag import project_service

    calls = []

    def fake(query, corpus, count):
        calls.append((query, corpus, count))
        return {"passages": [], "vide": True, "citation_imposee": True, "hitl": True}

    monkeypatch.setattr(project_service, "chercher_projet", fake)
    monkeypatch.setenv("MOTEUR", "rag")
    from serveur import chercher

    result = chercher("caution provisoire", "cps:2026/DTR/0123", 3)
    assert calls == [("caution provisoire", "cps:2026/DTR/0123", 3)]
    assert result["citation_imposee"] and result["hitl"]


def test_rag_backend_failure_has_no_lexical_or_other_corpus_fallback(monkeypatch):
    root = Path(__file__).resolve().parents[3]
    monkeypatch.syspath_prepend(str(root / "06-connaissances/astra-rag"))
    from sou9na_rag import project_service

    def fail(*args):
        raise RuntimeError("secret-token")

    monkeypatch.setattr(project_service, "chercher_projet", fail)
    monkeypatch.setenv("MOTEUR", "rag")
    result = moteur_recherche.chercher("question", "reglementation")
    assert result["erreur"] == "rag_indisponible"
    assert not result["passages"] and result["hitl"]
    assert "secret" not in str(result)
