# =====================================================================
# Tests CPS (déterministes, sans réseau, sans DB).
# =====================================================================
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import cps_extract, cps_ingest


FIXTURE = Path(__file__).parent / "fixtures" / "cps_fixture.pdf"


def test_fixture_exists():
    assert FIXTURE.exists(), "fixture cps_fixture.pdf manquante"


def test_extract_text_pypdf():
    data = FIXTURE.read_bytes()
    info = cps_extract.extract_text(data)
    assert info["extraction"] == "pypdf"
    assert info["pages"] == 1
    assert info["char_count"] >= 100
    assert len(info["sha256"]) == 64
    assert "Article 1" in info["text"]


def test_split_into_sections():
    data = FIXTURE.read_bytes()
    info = cps_extract.extract_text(data)
    secs = cps_extract.split_into_sections(info["text"])
    assert len(secs) == 5
    titles = [s["titre"] for s in secs]
    assert any("Article 1" in (t or "") for t in titles)
    assert any("Article 51-2" in (t or "") for t in titles)
    # chaque section a du texte et un section_no unique
    nos = [s["section_no"] for s in secs]
    assert nos == list(range(1, len(secs) + 1))
    for s in secs:
        assert s["texte"].strip()
        assert s["pages_section"] == "p. 1"


def test_empty_text_returns_no_sections():
    assert cps_extract.split_into_sections("") == []
    assert cps_extract.split_into_sections("   ") == []


def test_no_headers_single_section():
    secs = cps_extract.split_into_sections("Texte libre sans titre numéroté.")
    assert len(secs) == 1
    assert secs[0]["section_no"] == 1
    assert "Texte libre" in secs[0]["texte"]


def test_ocr_fallback_graceful(monkeypatch):
    # Si pypdf donne < 100 chars et l'OCR est indisponible, on garde pypdf.
    monkeypatch.setattr(cps_extract, "extract_with_pypdf", lambda d: ("court", 1))
    monkeypatch.setattr(cps_extract, "extract_with_ocr",
                        lambda d: (_ for _ in ()).throw(ImportError("no tesseract")))
    info = cps_extract.extract_text(b"%PDF-1.4")
    assert info["extraction"].startswith("pypdf")
    assert info["text"] == "court"


def test_size_guard(monkeypatch):
    monkeypatch.setattr(cps_ingest.db, "tender_document_by_reference", lambda ref: None)
    big = b"x" * (26 * 1024 * 1024)
    res = cps_ingest.ingest_cps("REF-X", big)
    assert res["status"] == "skipped"
    assert res["reason"] == "too_large"


def test_cps_status_missing(monkeypatch):
    import db_cps as dbmod
    monkeypatch.setattr(dbmod, "tender_document_by_reference", lambda ref: None)
    monkeypatch.setattr(dbmod, "query", lambda sql, params=(): [{"n": 0}])
    res = dbmod.cps_status("REF-X")
    assert res["has_document"] is False
    assert res["statut"] == "missing_cps"
    assert res["sections"] == 0