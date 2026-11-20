# ═══════════════════════════════════════════════════════════════════
# Tests A2A — avec un « agent » local réel sur HTTP (http.server).
# Vérifie : cartes bien formées, lookup par compétence, appel JSON-RPC,
# parsing de la réponse, comportement en erreur. Zéro réseau externe.
# ═══════════════════════════════════════════════════════════════════
import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from a2a_client import (
    CARTES_DIR,
    A2AError,
    appeler_a2a,
    charger_cartes,
    trouver_carte,
)

# ── Un faux agent INSPECTEUR sur HTTP (répond via A2A message/send) ──
RAPPORT = {"avis_nouveaux": 137, "doublons": 2, "rejetes": 4, "source": "portail"}


class FauxAgent(BaseHTTPRequestHandler):
    def log_message(self, *_args):
        pass

    def do_POST(self):                                        # noqa: N802
        longueur = int(self.headers.get("Content-Length", 0))
        requete = json.loads(self.rfile.read(longueur))
        assert requete["method"] == "message/send"
        assert self.headers["X-Internal-Token"] == "token-test-a2a"
        corps = {
            "jsonrpc": "2.0",
            "id": requete.get("id"),
            "result": {
                "artifacts": [{"parts": [{"kind": "data", "data": dict(RAPPORT)}]}]
            },
        }
        reponse = json.dumps(corps).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(reponse)))
        self.end_headers()
        self.wfile.write(reponse)


@pytest.fixture(scope="module")
def faux_agent():
    serveur = HTTPServer(("127.0.0.1", 0), FauxAgent)
    port = serveur.server_address[1]
    thread = threading.Thread(target=serveur.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    serveur.shutdown()


# ── Les 6 cartes du dépôt sont des JSON valides et bien formés ──────
def test_les_6_cartes_existent():
    fichiers = sorted(p.name for p in CARTES_DIR.glob("*.agent-card.json"))
    assert fichiers == ["compagnon.agent-card.json", "concierge.agent-card.json",
                        "inspecteur.agent-card.json", "juge.agent-card.json",
                        "regisseur.agent-card.json", "sentinelle.agent-card.json"]


def test_champs_obligatoires_de_chaque_carte():
    for carte in charger_cartes().values():
        c = carte["carte"]
        for cle in ("name", "description", "url", "version", "skills",
                    "securitySchemes", "defaultInputModes", "defaultOutputModes"):
            assert c.get(cle), f"{carte['fichier']} : champ manquant {cle!r}"


def test_toutes_les_competences_du_graphe_ont_une_carte():
    cartes = charger_cartes()
    # Les 7 compétences appelées par le graphe / la plateforme :
    for competence in ("orchestrer", "collecte_avis", "calculer_match",
                       "composer_digest", "statuer", "distribuer_digests",
                       "observer_marche"):
        assert competence in cartes, competence


def test_lookup_carte_par_competence():
    carte = trouver_carte("collecte_avis")
    assert carte["agent"] == "INSPECTEUR"
    assert "url" in carte


def test_competence_inconnue_rejetee_proprement():
    with pytest.raises(A2AError, match="compétence inconnue"):
        trouver_carte("faire_faire_la_vaisselle")


# ── Appel A2A réel (contre le faux agent HTTP) ─────────────────────
def test_appel_a2a_message_send(faux_agent, monkeypatch):
    monkeypatch.setenv("A2A_URL_OVERRIDE_INSPECTEUR", faux_agent)
    monkeypatch.setenv("A2A_TOKEN", "token-test-a2a")
    # charger_cartes est appelé à chaque appel — la surcharge env est lue ici :
    resultat = asyncio.run(appeler_a2a("collecte_avis", {"mode": "cron", "date": "2026-11-17"}))
    assert resultat == RAPPORT


def test_appel_a2a_agent_en_panne(monkeypatch):
    monkeypatch.setenv("A2A_URL_OVERRIDE_INSPECTEUR", "http://127.0.0.1:1")
    with pytest.raises(A2AError, match="agent indisponible"):
        asyncio.run(appeler_a2a("collecte_avis", {"mode": "cron", "date": "2026-11-17"},
                                timeout=2))
