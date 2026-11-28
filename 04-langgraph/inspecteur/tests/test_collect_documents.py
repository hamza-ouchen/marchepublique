import sys
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import collect_documents  # noqa: E402


def test_pdf_files_ignores_macos_metadata_in_zip():
    data = BytesIO()
    with ZipFile(data, "w") as archive:
        archive.writestr("dossier/CPS.pdf", b"%PDF-1.4\n")
        archive.writestr("__MACOSX/dossier/._CPS.pdf", b"\x00\x05\x16\x07")
        archive.writestr("dossier/._AVIS.pdf", b"\x00\x05\x16\x07")
    assert list(collect_documents.pdf_files("https://example.com/dossier.zip", data.getvalue())) == [
        ("CPS.pdf", b"%PDF-1.4\n"),
    ]


def test_run_documents_drains_queue_and_fetches_each_canonical_url_once(monkeypatch):
    lignes = [
        {"reference": "A/1", "source_url": "https://www.marchespublics.gov.ma/x?utm_source=a",
         "url_key": "https://marchespublics.gov.ma/x", "enrich_attempts": 0},
        {"reference": "B/1", "source_url": "https://marchespublics.gov.ma/x#frag",
         "url_key": "https://marchespublics.gov.ma/x", "enrich_attempts": 0},
    ]
    etats = [lignes, []]
    appels = []
    ecritures = []

    def faux_pending(company, date, *, all_tenders, batch_size):
        return etats.pop(0)

    def faux_fetch(tender, uploader):
        appels.append(tender["reference"])
        return tender["reference"], {"saved": 1, "signals": {"caution_mad": 1000}, "error": None}

    monkeypatch.setattr(collect_documents, "_pending", faux_pending)
    monkeypatch.setattr(collect_documents, "_fetch_one", faux_fetch)
    monkeypatch.setattr(collect_documents, "make_uploader", lambda: (lambda path, data: path))
    monkeypatch.setattr(collect_documents.db_cps, "execute",
                        lambda sql, params=(): ecritures.append((sql, params)))

    rapport = collect_documents.run_documents(
        "2026-11-23", "EXPLEO-IT-001", workers=1, all_tenders=True
    )

    assert appels == ["A/1"]                 # une seule URL canonique téléchargée
    assert len(ecritures) == 2               # les deux références sont marquées
    assert rapport["urls_uniques"] == 1
    assert rapport["documents_annonces"] == 2
    assert rapport["documents_ingerees"] == 2
    assert etats == []                       # file entièrement drainée


def test_failed_fetch_is_scheduled_with_backoff(monkeypatch):
    ecritures = []
    monkeypatch.setattr(collect_documents.db_cps, "execute",
                        lambda sql, params=(): ecritures.append((sql, params)))
    collect_documents._mark("A/1", {"error": "detail: 503", "attempts": 0})
    assert "enrich_next_at" in ecritures[0][0]
    assert ecritures[0][1][0] == 1


def test_daily_queue_switches_to_fallback_on_detail_outage(monkeypatch):
    tender = {"reference": "A/1", "source_url": "https://www.marchespublics.gov.ma/x"}
    batches = iter(([tender],))
    retry = []
    monkeypatch.setattr(collect_documents, "_pending", lambda *args, **kwargs: next(batches))
    monkeypatch.setattr(collect_documents, "make_uploader", lambda: object())
    monkeypatch.setattr(collect_documents, "_fetch_one", lambda row, uploader: (
        row["reference"], {"saved": 0, "error": "detail: ConnectTimeout"},
    ))
    monkeypatch.setattr(collect_documents, "_mark", lambda ref, result: retry.append(ref))

    report = collect_documents.run_documents("2026-11-24", "EXPLEO-IT-001", time_budget=60)

    assert report["source_documents"] == "portail_indisponible"
    assert report["documents_retry_scheduled"] == 1
    assert retry == ["A/1"]
