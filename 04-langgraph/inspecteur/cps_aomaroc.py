# =====================================================================
# REPLI aomaroc — uniquement si le portail national ne livre pas le
# dossier (indisponible ou formulaire en échec). Le relais aomaroc
# expose les MÊMES clés que les source_url stockées
# (refConsultation + orgAcronyme) :
#   POST /cps/lancer?ref=&org=  -> {id}
#   GET  /cps/etat?id=          -> etape: attente|connexion|formulaire|
#                                  telechargement|fini|erreur
#   GET  /cps/fichier?id=       -> ZIP du DCE complet
# =====================================================================
from __future__ import annotations

import time
from typing import Any
from urllib.parse import urlencode

import requests

from . import config

POLL_INTERVAL_S = 4.0
POLL_TIMEOUT_S = 180.0
JOB_RETRY = 1


class AomarocError(RuntimeError):
    """Le relais aomaroc n'a pas livré le dossier."""


def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64; SouknaBot/1.0)",
        "Referer": config.AO_BASE + "/",
    })
    return s


def launch_job(s: requests.Session, ref: str, org: str) -> str:
    url = f"{config.AO_BASE}/cps/lancer?{urlencode({'ref': ref, 'org': org})}"
    r = s.post(url, timeout=60)
    if r.status_code != 200:
        raise AomarocError(f"lancer http {r.status_code}")
    job_id = (r.json() or {}).get("id")
    if not job_id:
        raise AomarocError("lancer sans id de job")
    return job_id


def poll_job(s: requests.Session, job_id: str,
             timeout_s: float = POLL_TIMEOUT_S) -> dict[str, Any]:
    """Poll /cps/etat jusqu'à fini/erreur (timeout -> etape timeout)."""
    deadline = time.monotonic() + timeout_s
    url = f"{config.AO_BASE}/cps/etat?{urlencode({'id': job_id})}"
    while time.monotonic() < deadline:
        try:
            r = s.get(url, timeout=30)
            st = r.json() if r.status_code == 200 else {}
        except requests.RequestException:
            st = {}
        etape = st.get("etape")
        if etape in ("fini", "erreur"):
            return st
        time.sleep(POLL_INTERVAL_S)
    return {"etape": "timeout", "err": "poll_timeout"}


def fetch_relay_zip(session: requests.Session, refc: str, org: str,
                    timeout_s: float = POLL_TIMEOUT_S) -> bytes:
    """Lance le job aomaroc et télécharge le ZIP (1 relance sur erreur)."""
    s = _session()
    status: dict[str, Any] = {}
    job_id: str | None = None
    for _attempt in range(1 + JOB_RETRY):
        try:
            job_id = launch_job(s, refc, org)
        except (requests.RequestException, AomarocError) as exc:
            job_id = None
            status = {"etape": "erreur", "err": f"lancer: {str(exc)[:120]}"}
        if job_id:
            status = poll_job(s, job_id, timeout_s)
            if status.get("etape") == "fini":
                break
        time.sleep(3)
    if status.get("etape") != "fini" or not job_id:
        raise AomarocError(
            f"relais aomaroc: {status.get('etape')} {status.get('err') or ''}")
    url = f"{config.AO_BASE}/cps/fichier?{urlencode({'id': job_id})}"
    try:
        r = s.get(url, timeout=180)
    except requests.RequestException as exc:
        raise AomarocError(f"fichier: {str(exc)[:120]}") from exc
    if r.status_code != 200 or not r.content:
        raise AomarocError("zip aomaroc vide")
    return r.content
