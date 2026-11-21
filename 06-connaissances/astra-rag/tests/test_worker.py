"""Le worker conserve le rapport du lot et ne publie jamais un secret d'erreur."""

import json
import sys

from sou9na_rag import worker
from sou9na_rag.store import BackendError


def test_batch_continues_after_transaction_failure(monkeypatch, tmp_path):
    destination = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["worker", "cps", "--report", str(destination)])
    monkeypatch.setattr(worker.Settings, "from_env", lambda: None)
    monkeypatch.setattr(worker, "ProjectStore", lambda settings: None)

    class Repository:
        def pending(self, limit):
            return [1, 2]

    def ingest(repository, store, document_id):
        if document_id == 1:
            raise BackendError("SUPABASE_TRANSACTION_FAILED")
        return {"document_id": 2, "status": "ready"}

    monkeypatch.setattr(worker, "CpsRepository", Repository)
    monkeypatch.setattr(worker, "ingest_cps", ingest)
    assert worker.main() == 1
    result = json.loads(destination.read_text(encoding="utf-8"))
    assert [d["status"] for d in result["documents"]] == ["failed", "ready"]


def test_configuration_error_produces_sanitized_report(monkeypatch, tmp_path, capsys):
    destination = tmp_path / "report.json"
    monkeypatch.setattr(sys, "argv", ["worker", "cps", "--report", str(destination)])

    def fail():
        raise ValueError("secret-dsn-must-not-escape")

    monkeypatch.setattr(worker.Settings, "from_env", fail)
    assert worker.main() == 1
    assert "secret" not in destination.read_text(encoding="utf-8")
    assert "secret" not in capsys.readouterr().out
