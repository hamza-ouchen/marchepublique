from __future__ import annotations

import pytest

from inspecteur import config, cps_collect, cps_download, cps_extract, db, storage

CANDIDATES = [
    {"reference": "REF-1", "source_url": "https://portail.ma/avis/1",
     "secteur": "construction", "region": "Casablanca", "montant_mad": 1_500_000,
     "date_remise": "2026-12-01", "statut": "ouvert"},
    {"reference": "REF-2", "source_url": "https://portail.ma/avis/2",
     "secteur": "informatique", "region": "Casablanca", "montant_mad": 800_000,
     "date_remise": "2026-12-02", "statut": "ouvert"},
    {"reference": "REF-3", "source_url": "https://portail.ma/avis/3",
     "secteur": "construction", "region": "Casablanca", "montant_mad": 900_000,
     "date_remise": "2026-10-01", "statut": "clos"},
]
PDF = b"%PDF-1.4 " + (b"Article 1 - contenu de test. " * 20)
INFO = {"text": "Article 1\n" + ("Du texte suffisamment long. " * 20),
        "pages": 1, "extraction": "pypdf", "sha256": "a" * 64, "char_count": 600}
SECTIONS = [{"section_no": 1, "numero": "1", "titre": "Article 1",
             "texte": "Du texte", "pages_section": "p. 1"}]


@pytest.fixture
def fake_env(monkeypatch):
    inserted: list[dict] = []
    monkeypatch.setattr(db, "ensure_schema", lambda: None)
    monkeypatch.setattr(db, "active_profiles", lambda: [
        {"secteur": "construction", "region": "casa-settat", "capacite_mad": 3_000_000}])
    monkeypatch.setattr(db, "candidate_tenders", lambda limit=500: list(CANDIDATES))
    monkeypatch.setattr(db, "usage_bytes", lambda: 0)
    monkeypatch.setattr(db, "document_for", lambda ref: None)
    monkeypatch.setattr(db, "sha_exists", lambda sha: False)
    monkeypatch.setattr(db, "insert_document",
                        lambda **kw: inserted.append(kw) or len(inserted))
    monkeypatch.setattr(db, "replace_sections", lambda doc_id, sections: len(sections))
    monkeypatch.setattr(cps_download, "fetch_detail",
                        lambda url, **kw: "<a href='https://portail.ma/f.pdf'>CPS</a>")
    monkeypatch.setattr(cps_download, "download_pdf", lambda url, **kw: PDF)
    monkeypatch.setattr(cps_extract, "extract_text", lambda data: dict(INFO))
    monkeypatch.setattr(cps_extract, "split_into_sections", lambda text: list(SECTIONS))
    monkeypatch.setattr(storage, "make_uploader", lambda *a, **k: None)
    monkeypatch.setattr(config, "PORTAL_DELAY_S", 0)
    monkeypatch.setattr(config, "ALLOWED_HOSTS", [])  # fixtures sur portail.ma
    return inserted


def test_insere_uniquement_le_document_pertinent(fake_env):
    stats = cps_collect.collect(max_docs=5)
    assert len(fake_env) == 1
    assert stats["inseres"][0]["reference"] == "REF-1"
    assert stats["filtres"]["secteur_hors_cible"] == 1
    assert stats["filtres"]["statut_clos"] == 1
    assert stats["echecs"] == []
    assert stats["selectionnes"] == 1


def test_idempotence(fake_env, monkeypatch):
    monkeypatch.setattr(db, "document_for",
                        lambda ref: {"statut": "extracted"} if ref == "REF-1" else None)
    stats = cps_collect.collect(max_docs=5)
    assert fake_env == []
    assert stats["ignores"]["deja_ingere"] == 1


def test_budget_bloque_l_insertion(fake_env):
    stats = cps_collect.collect(max_docs=5, max_bytes=10)
    assert fake_env == []
    assert stats["ignores"]["budget_insuffisant_pdf"] == 1


def test_dry_run_sans_ecriture(fake_env):
    stats = cps_collect.collect(dry_run=True, max_docs=5)
    assert fake_env == []
    assert stats["inseres"][0]["statut"].startswith("dry_run:")


def test_arret_si_portail_indisponible(fake_env, monkeypatch):
    monkeypatch.setattr(config, "MAX_CONSECUTIVE_FAILURES", 1)

    def boom(url, **kw):
        raise cps_download.FetchError("portail indisponible")

    monkeypatch.setattr(cps_download, "fetch_detail", boom)
    stats = cps_collect.collect(max_docs=5)
    assert fake_env == []
    assert stats["ignores"]["portail_indisponible"] == 1
    assert len(stats["echecs"]) == 1
