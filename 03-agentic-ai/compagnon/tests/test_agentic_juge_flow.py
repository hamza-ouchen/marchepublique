# Test du client de flow JUGE : URL complète, clé dédiée, timeout et parsing.
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


def test_run_juge_flow_utilise_url_et_cle_dediees(monkeypatch):
    capture = {}

    monkeypatch.setenv("AGENTIC_JUGE_URL", "https://agentic.test/api/v1/run/juge")
    monkeypatch.setenv("AGENTIC_JUGE_API_KEY", "cle-juge")
    monkeypatch.setenv("AGENTIC_API_KEY", "cle-generique")

    def faux_urlopen(requete, timeout):
        capture["url"] = requete.full_url
        capture["authorization"] = requete.headers["Authorization"]
        capture["timeout"] = timeout
        capture["corps"] = json.loads(requete.data.decode("utf-8"))
        return _Reponse({"outputs": [{"text": '{"status":"blocked"}'}]})

    monkeypatch.setattr(urllib.request, "urlopen", faux_urlopen)
    ok, texte = agentic_flow.run_juge_flow("2026-11-26", "EXPLEO-IT-001", timeout=9)

    assert ok is True
    assert "blocked" in texte
    assert capture["url"] == "https://agentic.test/api/v1/run/juge"
    assert capture["authorization"] == "Bearer cle-juge"
    assert capture["timeout"] == 9
    assert "EXPLEO-IT-001" in capture["corps"]["input_value"]


def test_run_juge_flow_timeout_renvoie_false(monkeypatch):
    monkeypatch.setenv("AGENTIC_JUGE_URL", "https://agentic.test/api/v1/run/juge")
    monkeypatch.setenv("AGENTIC_JUGE_API_KEY", "cle-juge")

    def faux_urlopen(_requete, timeout):
        raise TimeoutError("timeout")

    monkeypatch.setattr(urllib.request, "urlopen", faux_urlopen)
    ok, texte = agentic_flow.run_juge_flow("2026-11-26", "EXPLEO-IT-001", timeout=1)
    assert ok is False
    assert "TimeoutError" in texte
