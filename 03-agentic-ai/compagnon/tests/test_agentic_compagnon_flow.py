# Le client MATCHING ne doit accepter qu'un lot de scores réellement calculé.
import json
import urllib.request

import agentic_flow


class _Reponse:
    def __init__(self, payload):
        self.payload = json.dumps(payload).encode("utf-8")

    def read(self):
        return self.payload

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


def _configurer(monkeypatch, payload):
    monkeypatch.setenv("AGENTIC_BASE_URL", "https://agentic.test")
    monkeypatch.setenv("AGENTIC_MATCHING_FLOW_ID", "matching-test")
    monkeypatch.setenv("AGENTIC_API_KEY", "cle-test")
    monkeypatch.setattr(
        urllib.request, "urlopen",
        lambda _requete, timeout: _Reponse({"outputs": [{"text": json.dumps(payload)}]}),
    )


def test_run_compagnon_accepte_un_lot_calcule(monkeypatch):
    _configurer(monkeypatch, {
        "source": "flow_compagnon", "scores_calcules": 177, "scores_ecrits": 0,
    })
    ok, detail = agentic_flow.run_compagnon("EXPLEO-IT-001", "2026-11-26", 5)
    assert ok is True
    assert "177" in detail


def test_run_compagnon_refuse_un_lot_sans_score(monkeypatch):
    _configurer(monkeypatch, {
        "source": "flow_compagnon", "scores_calcules": 0, "scores_ecrits": 0,
    })
    ok, detail = agentic_flow.run_compagnon("EXPLEO-IT-001", "2026-11-26", 5)
    assert ok is False
    assert "inattendue" in detail
