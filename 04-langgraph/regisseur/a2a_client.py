# ═══════════════════════════════════════════════════════════════════
# SOU9NA — RÉGISSEUR · client A2A (Agent-to-Agent, JSON-RPC message/send)
#
# Principe : on ne « code en dur » jamais l'emplacement d'un agent —
# on cherche d'abord sa CARTE (compétence), puis on l'appelle.
# Les cartes vivent dans 03-agentic-ai/agent-cards/ et sont servies par
# chaque agent sur GET /.well-known/agent-card.json.
#
# Mode demo : aucun appel réseau — le nœud rend un rapport simulé.
# Mode reel : un agent indisponible = ERREUR BRUTE (jamais de bluff).
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

import httpx

CARTES_DIR = Path(__file__).resolve().parents[2] / "03-agentic-ai" / "agent-cards"


class A2AError(Exception):
    """Échec d'appel A2A (carte absente, agent en panne, réponse illisible)."""


# Temps morts adaptés au coût réel de chaque étape : la collecte PDF et le
# flow de scoring sont lents, la composition/distribution sont rapides.
TIMEOUTS_PAR_SKILL = {
    "collecte_avis": 1800.0,
    "collecter_documents": 1800.0,
    "calculer_match": 900.0,
    "statuer": 900.0,
    "composer_digest": 300.0,
    "distribuer_digests": 300.0,
}


def charger_cartes(chemin: str | None = None) -> dict[str, dict]:
    """Charge toutes les cartes → index par skill_id."""
    dossier = Path(chemin) if chemin else CARTES_DIR
    if not dossier.is_dir():
        raise A2AError(f"dossier de cartes introuvable : {dossier}")
    cartes: dict[str, dict] = {}
    for fichier in sorted(dossier.glob("*.agent-card.json")):
        try:
            carte = json.loads(fichier.read_text(encoding="utf-8"))
        except json.JSONDecodeError as err:
            raise A2AError(f"carte invalide : {fichier.name} — {err}") from err
        nom = carte.get("name") or fichier.stem
        url = _url_agent(carte)
        for skill in carte.get("skills", []):
            cartes[skill["id"]] = {
                "fichier": fichier.name,
                "agent": nom,
                "url": url,
                "skill_id": skill["id"],
                "carte": carte,
            }
    return cartes


def _slugifie(nom: str) -> str:
    """INSPECTEUR, COMPAGNON… : sans accents, majuscules, tirets→_."""
    import unicodedata

    decompose = unicodedata.normalize("NFD", nom or "")
    sans_accents = "".join(c for c in decompose if unicodedata.category(c) != "Mn")
    return sans_accents.upper().replace("-", "_").replace(" ", "_")


def _url_agent(carte: dict) -> str:
    """URL de base du service de l'agent — surchargeable par variable d'env.

    Priorité (style Coach) :  <SLUG>_URL  →  A2A_URL_OVERRIDE_<SLUG>  →  la carte.
    """
    slug = _slugifie(carte.get("name") or "")
    override = os.environ.get(f"{slug}_URL") or os.environ.get(f"A2A_URL_OVERRIDE_{slug}")
    return (override or carte.get("url", "")).rstrip("/")


def _token_agent(carte: dict) -> str:
    """Token d'appel de l'agent — par priorité, style Coach :
    <SLUG>_TOKEN  →  token partagé A2A_TOKEN.
    """
    slug = _slugifie(carte.get("name") or "")
    return os.environ.get(f"{slug}_TOKEN") or os.environ.get("A2A_TOKEN", "")


def trouver_carte(skill_id: str, chemin: str | None = None) -> dict:
    cartes = charger_cartes(chemin)
    cible = cartes.get(skill_id)
    if cible is None:
        raise A2AError(
            f"compétence inconnue : {skill_id!r} — cartes disponibles : "
            f"{sorted(cartes)}"
        )
    return cible


def _extraire_data(corps: dict) -> dict:
    """Extrait l'objet `data` du résultat A2A, quel que soit le nid exact."""
    resultat = corps.get("result", corps)
    # Forme A2A : result.artifacts[0].parts[] avec kind=data
    for artefact in resultat.get("artifacts", []) if isinstance(resultat, dict) else []:
        for part in artefact.get("parts", []):
            if part.get("kind") == "data" and isinstance(part.get("data"), dict):
                return part["data"]
    # Formes tolérées : result.data / result.message.parts[0].data
    if isinstance(resultat, dict):
        if isinstance(resultat.get("data"), dict):
            return resultat["data"]
        message = resultat.get("message", {})
        for part in message.get("parts", []) if isinstance(message, dict) else []:
            if isinstance(part.get("data"), dict):
                return part["data"]
    raise A2AError(f"réponse A2A sans données exploitables : {json.dumps(corps)[:300]}")


async def appeler_a2a(skill_id: str, donnees: dict,
                      timeout: float | None = None,
                      chemin_cartes: str | None = None) -> dict:
    """Appelle l'agent qui expose `skill_id` (carte → URL → JSON-RPC)."""
    cible = trouver_carte(skill_id, chemin_cartes)
    timeout = timeout or float(os.environ.get(
        f"A2A_TIMEOUT_{skill_id.upper()}",
        os.environ.get(f"A2A_TIMEOUT_{skill_id.upper()}_S",
                       TIMEOUTS_PAR_SKILL.get(skill_id,
                                              float(os.environ.get("A2A_TIMEOUT_S", "120")))),
    ))
    payload = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {
            "message": {
                "role": "user",
                "parts": [{"kind": "data", "data": donnees}],
                "metadata": {"skill_id": skill_id},
            }
        },
    }
    headers = {"Content-Type": "application/json"}
    token = _token_agent(cible["carte"])
    if token:
        headers["X-Internal-Token"] = token

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            reponse = await client.post(cible["url"] + "/", json=payload, headers=headers)
            reponse.raise_for_status()
            corps = reponse.json()
    except httpx.HTTPStatusError as err:
        raise A2AError(f"{skill_id} ({cible['agent']}) : HTTP {err.response.status_code} — "
                       f"{err.response.text[:200]}") from err
    except httpx.HTTPError as err:
        raise A2AError(f"{skill_id} ({cible['agent']}) : agent indisponible — "
                       f"{type(err).__name__}: {err!r} ({cible['url']})") from err

    if "error" in corps:
        raise A2AError(f"{skill_id} ({cible['agent']}) : erreur agent — "
                       f"{json.dumps(corps['error'])[:300]}")
    return _extraire_data(corps)
