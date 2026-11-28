# =====================================================================
# COMPAGNON — déclencheur du flow hébergé sur la plateforme Agentic.
#
# Module historique conservé pour les workflows isolés.
# Le scoring actif utilise score_local.py via le service COMPAGNON A2A.
# =====================================================================
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request


def _load_env() -> None:
    from pathlib import Path
    env = Path(__file__).resolve().parents[2] / "02-backend" / ".env"
    if not env.is_file():
        return
    for line in env.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _texts(obj, out: list[str]) -> None:
    if isinstance(obj, dict):
        text = obj.get("text")
        if isinstance(text, str) and text:
            out.append(text)
        for value in obj.values():
            _texts(value, out)
    elif isinstance(obj, list):
        for value in obj:
            _texts(value, out)


def _url_flow(flow_id: str | None, url_complete: str | None, base: str) -> str | None:
    """URL complète fournie par l'utilisateur, sinon base + ID de flow."""
    if url_complete:
        return url_complete
    if not flow_id:
        return None
    return base.rstrip("/") + "/api/v1/run/" + flow_id


def _tweaks_depuis_env(nom: str, defaut: dict) -> dict:
    """Surcharge JSON optionnelle des tweaks Langflow d'un flow."""
    brut = os.environ.get(nom)
    if not brut:
        return defaut
    try:
        valeur = json.loads(brut)
    except ValueError:
        return defaut
    return valeur if isinstance(valeur, dict) else defaut


def _est_log(texte: str) -> bool:
    """La plateforme renvoie parfois ses logs dans les champs `text`."""
    if "\x1b[" in texte or re.search(r"^\s*\d{4}-\d{2}-\d{2}T", texte):
        return True
    return any(marqueur in texte for marqueur in (
        " sent GET ", " sent POST ", "client=", "user_id=", "username=",
        "method=", "path=", "email=",
    ))


def _texte_concierge_valide(textes: list[str]) -> str | None:
    """Extrait une réponse utilisable ; rejette logs, tables et sorties d'agent."""
    invalides = (
        "erreur_technique", "agent_garde", "self-critique", "je suis claude",
        "je ne peux pas", "veuillez confirmer", "brouillon final relu",
    )

    def nettoyer(brut: str) -> str:
        texte = brut.strip()
        if texte.startswith("```"):
            for partie in texte.split("```"):
                candidate = partie.strip()
                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate.startswith("{"):
                    return candidate
        return texte

    # 1. Priorité absolue : objet JSON avec un champ `texte`.
    for brut in textes:
        texte = nettoyer(brut)
        if not texte.startswith("{"):
            continue
        try:
            objet = json.loads(texte)
        except ValueError:
            continue
        if not isinstance(objet, dict):
            continue
        candidat = objet.get("texte")
        if isinstance(candidat, str) and candidat.strip():
            return candidat.strip()

    # 2. Sinon, premier texte brut qui n'est pas un log ni une table.
    for brut in textes:
        texte = nettoyer(brut)
        if not texte or texte.startswith("|") or _est_log(texte):
            continue
        if texte.lower().startswith("allowed"):
            texte = texte[len("allowed"):].lstrip(" :\n\t")
        if texte.lower().startswith("blocked:"):
            return "je verifie et je reviens vers vous"
        if not texte or any(mot in texte.lower() for mot in invalides):
            continue
        if texte.startswith("|"):
            continue
        return texte
    return None


def _objets_json(textes: list[str]):
    """Extrait les objets JSON même si la plateforme ajoute des logs autour."""
    decodeur = json.JSONDecoder()
    for brut in textes:
        texte = brut.strip()
        if texte.startswith("```"):
            for partie in texte.split("```"):
                candidate = partie.strip()
                if candidate.lower().startswith("json"):
                    candidate = candidate[4:].strip()
                if candidate.startswith("{"):
                    texte = candidate
                    break
        for position, caractere in enumerate(texte):
            if caractere != "{":
                continue
            try:
                objet, fin = decodeur.raw_decode(texte[position:])
            except ValueError:
                continue
            if isinstance(objet, dict):
                yield objet, texte[position:position + fin]


def run_compagnon(company_id: str, collecte: str, timeout: int = 900) -> tuple[bool, str]:
    _load_env()
    token = os.environ.get("AGENTIC_API_KEY")
    base = os.environ.get("AGENTIC_BASE_URL", "https://stg-agentic.abafusion.ai")
    url = _url_flow(
        os.environ.get("AGENTIC_MATCHING_FLOW_ID"),
        os.environ.get("AGENTIC_MATCHING_URL"),
        base,
    )
    if not token or not url:
        return False, "configuration Agentic MATCHING manquante"

    message = json.dumps(
        {"company_id": company_id, "date_collecte": collecte}, ensure_ascii=False
    )
    tweaks = _tweaks_depuis_env(
        "AGENTIC_MATCHING_TWEAKS",
        {"MCP Tools": {"limite": 100, "offset": 0}},
    )
    body = json.dumps({
        "input_value": message,
        "input_type": "chat",
        "output_type": "chat",
        "tweaks": tweaks,
    }).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "Sou9na-Pipeline/1.0",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        return False, f"appel flow Agentic échoué : {exc}"

    found: list[str] = []
    _texts(payload, found)
    unique: list[str] = []
    for text in found:
        if text not in unique:
            unique.append(text)
    for objet, brut in _objets_json(unique):
        if objet.get("source") != "flow_compagnon" or objet.get("erreur"):
            continue
        try:
            calcules = int(objet.get("scores_calcules") or objet.get("scores_ecrits") or 0)
        except (TypeError, ValueError):
            continue
        if calcules > 0:
            return True, brut
    return False, "réponse flow inattendue : " + " | ".join(unique[-3:])[:600]


def run_concierge_flow(company_id: str, message: str, date_collecte: str | None = None,
                       timeout: int = 90) -> tuple[bool, str]:
    """Déclenche le flow CONCIERGE hébergé, sans bloquer la réponse UI.

    Le flow est appelé en tâche de fond par l'API : si sa base MCP est
    indisponible, l'utilisateur reçoit quand même la réponse déterministe.
    """
    _load_env()
    token = os.environ.get("AGENTIC_API_KEY")
    base = os.environ.get("AGENTIC_BASE_URL", "https://stg-agentic.abafusion.ai")
    url = _url_flow(
        os.environ.get("AGENTIC_CONCIERGE_FLOW_ID"),
        os.environ.get("AGENTIC_CONCIERGE_URL"),
        base,
    )
    if not token or not url:
        return False, "configuration Agentic CONCIERGE manquante"

    contenu = json.dumps({
        "message": message,
        "company_id": company_id,
        "date_collecte": date_collecte,
    }, ensure_ascii=False)
    tweaks = _tweaks_depuis_env(
        "AGENTIC_CONCIERGE_TWEAKS",
        {"MCP Tools": {"limite": 100, "offset": 0}},
    )
    corps = json.dumps({
        "input_value": contenu,
        "input_type": "chat",
        "output_type": "chat",
        "tweaks": tweaks,
    }).encode("utf-8")
    requete = urllib.request.Request(
        url,
        data=corps, method="POST",
        headers={"Authorization": "Bearer " + token,
                 "Content-Type": "application/json",
                 "User-Agent": "Sou9na-Concierge/1.0"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:
            charge = reponse.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:600]}"
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        return False, f"appel flow CONCIERGE échoué : {type(exc).__name__}: {exc}"

    try:
        payload = json.loads(charge) if charge else {}
    except ValueError:
        payload = {}
    trouve: list[str] = []
    _texts(payload, trouve)
    texte = _texte_concierge_valide(list(dict.fromkeys(trouve)))
    if not texte:
        return False, "réponse flow CONCIERGE invalide"
    return True, texte[:2000]


def run_juge_flow(date_collecte: str, company_id: str,
                  timeout: int | None = None) -> tuple[bool, str]:
    """Flow Agentic JUGE — revue documentaire avant les verdicts locaux.

    Le flow attaché (workflowJugeVf) produit une revue contrainte et ne publie
    pas directement en base. Le JUGE LangGraph reste donc l'écrivain des
    verdicts ; ce client est appelé en premier par le RÉGISSEUR, avec repli
    automatique sur l'agent A2A en cas de timeout / HTTP error / réponse vide.
    """
    _load_env()
    token = os.environ.get("AGENTIC_JUGE_API_KEY") or os.environ.get("AGENTIC_API_KEY")
    base = os.environ.get("AGENTIC_BASE_URL", "https://stg-agentic.abafusion.ai")
    url = _url_flow(
        os.environ.get("AGENTIC_JUGE_FLOW_ID"),
        os.environ.get("AGENTIC_JUGE_URL"),
        base,
    )
    if not token or not url:
        return False, "configuration Agentic JUGE manquante"
    if timeout is None:
        try:
            timeout = int(os.environ.get("SOU9NA_AGENTIC_TIMEOUT", "900"))
        except ValueError:
            timeout = 900

    contenu = json.dumps(
        {"date_collecte": date_collecte, "company_id": company_id}, ensure_ascii=False
    )
    # Le composant MCP Tools du flow JUGE attend `limite`/`offset` comme
    # entiers. Sans tweak, la plateforme envoie des chaînes vides et échoue
    # avec une erreur Pydantic avant même d'appeler l'outil.
    tweaks = _tweaks_depuis_env(
        "AGENTIC_JUGE_TWEAKS",
        {"MCP Tools": {"limite": 100, "offset": 0}},
    )
    corps = json.dumps({
        "input_value": contenu,
        "input_type": "chat",
        "output_type": "chat",
        "tweaks": tweaks,
    }).encode("utf-8")
    requete = urllib.request.Request(
        url,
        data=corps,
        method="POST",
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
            "User-Agent": "Sou9na-Juge/1.0",
        },
    )
    try:
        with urllib.request.urlopen(requete, timeout=timeout) as reponse:
            charge = reponse.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return False, f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')[:600]}"
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        return False, f"appel flow JUGE échoué : {type(exc).__name__}: {exc}"

    try:
        payload = json.loads(charge) if charge else {}
    except ValueError:
        payload = {}
    trouve: list[str] = []
    _texts(payload, trouve)
    textes = list(dict.fromkeys(trouve))
    if not textes:
        return False, "réponse flow JUGE vide"
    for objet, brut in _objets_json(textes):
        if "status" in objet:
            return True, brut
    return True, " | ".join(textes)[:2000]
