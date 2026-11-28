"""Pont FastAPI -> RÉGISSEUR.

FastAPI est le point d'entrée : il ne fait que mettre un job en file.
Le vrai travail appartient au RÉGISSEUR (A2A), puis à ses agents
INSPECTEUR / COMPAGNON / JUGE. Aucun pipeline local n'est lancé ici.
"""
from __future__ import annotations

import json
import logging
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path

import psycopg

# Charger .env avant d'importer les modules DB. Le token A2A et les URLs
# d'agents vivent dans le .env du RÉGISSEUR : on charge les deux fichiers.
_ROOT = Path(__file__).resolve().parents[1]
for _env_path in (_ROOT / "02-backend" / ".env",
                  _ROOT / "04-langgraph" / "regisseur" / ".env"):
    if not _env_path.is_file():
        continue
    for _line in _env_path.read_text(encoding="utf-8-sig").splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _key, _value = _line.split("=", 1)
            os.environ.setdefault(_key.strip(), _value.strip())

from daily_jobs import claim, finish, mark_init  # noqa: E402
import db_cps  # noqa: E402

ROOT = _ROOT


def _resolve_mode(job: dict) -> str:
    """auto = premier remplissage (full) si la base est encore pauvre."""
    mode = (job.get("mode") or "auto").strip()
    if mode != "auto":
        return mode
    try:
        count = db_cps.query("SELECT count(*) AS n FROM public.tenders")[0]["n"]
    except Exception:
        count = 0
    return "full" if count < 1000 else "incremental"


def _mode_regisseur(mode: str) -> tuple[str, str]:
    """(mode de gate, consigne de collecte pour INSPECTEUR)."""
    if mode == "full":
        return "backfill", "full"
    if mode == "none":
        return "cron", "none"
    return "cron", "incremental"


def _appeler_regisseur(job: dict) -> dict:
    mode_gate, collecte_defaut = _mode_regisseur(_resolve_mode(job))
    collecte = (job.get("collecte") or "auto").strip()
    if collecte == "auto":
        collecte = collecte_defaut
    date = job["run_date"].isoformat()
    company = job["company_id"]
    url = os.getenv("A2A_REGISSEUR_URL", "http://127.0.0.1:8100").rstrip("/")
    token = os.getenv("A2A_TOKEN", "")
    timeout = float(os.getenv("A2A_REGISSEUR_TIMEOUT", "3600"))

    charge = {
        "jsonrpc": "2.0",
        "id": str(uuid.uuid4()),
        "method": "message/send",
        "params": {"message": {"role": "user", "parts": [{
            "kind": "data",
            "data": {
                "mode": mode_gate,
                "date": date,
                "company_id": company,
                "request_id": str(uuid.uuid4()),
                "run_id": f"run-{date}-{mode_gate}-{uuid.uuid4().hex[:6]}",
                "source": "cron",
                "collecte": collecte,
            },
        }]}},
    }
    en_tete = {"Content-Type": "application/json"}
    if token:
        en_tete["X-Internal-Token"] = token

    requete = urllib.request.Request(
        url + "/", data=json.dumps(charge).encode("utf-8"),
        headers=en_tete, method="POST")
    with urllib.request.urlopen(requete, timeout=timeout) as reponse:
        corps = json.loads(reponse.read().decode("utf-8"))
    if "error" in corps:
        raise RuntimeError(f"RÉGISSEUR : {corps['error']}")

    try:
        rapport = corps["result"]["artifacts"][0]["parts"][0]["data"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(f"réponse A2A illisible : {str(corps)[:300]}") from exc
    if rapport.get("statut") in ("echec", "rejete") or rapport.get("erreurs"):
        raise RuntimeError(
            f"run {rapport.get('statut')} — erreurs : {rapport.get('erreurs')}")
    return rapport


def run_job(job: dict) -> None:
    logging.info("Daily workflow %s — %s — délégation au RÉGISSEUR",
                 job.get("run_date"), job.get("company_id"))
    exc: Exception | None = None
    rapport: dict = {}
    try:
        rapport = _appeler_regisseur(job)
        logging.info("RÉGISSEUR terminé : %s", json.dumps(rapport.get("rapport", {}),
                                                          ensure_ascii=False)[:1500])
        exit_code = 0
    except (urllib.error.URLError, OSError, RuntimeError, ValueError, TimeoutError) as erreur:
        exc = erreur
        logging.exception("Workflow RÉGISSEUR en échec : %s", erreur)
        exit_code = 1

    try:
        mark_init(job["company_id"], "ready" if exit_code == 0 else "error",
                  None if exit_code == 0 else str(exc))
    except Exception:                                # noqa: BLE001
        logging.exception("Impossible de mettre à jour init_status")

    try:
        identifiant = db_cps.query_write(
            """
            INSERT INTO lg_requests
              (message_id, sender_phone, route, outcome, error, finished_at, latency_ms)
            VALUES (%s,%s,'pipeline',%s,%s,now(),0) RETURNING id::text AS id
            """,
            (f"run-{job['run_date']}-{job['company_id']}", job["company_id"],
             "ok" if exit_code == 0 else "error",
             None if exit_code == 0 else str(exc)[:300]),
        )[0]["id"]
        db_cps.execute(
            "INSERT INTO lg_logs (request_id, agent, duration_s, detail) VALUES (%s,%s,%s,%s)",
            (identifiant, "regisseur", 0.0,
             json.dumps(rapport if exit_code == 0 else {"erreur": str(exc)[:300]},
                        ensure_ascii=False)[:500]),
        )
    except Exception:                                # noqa: BLE001
        logging.exception("Impossible d'écrire la trace du run")
        identifiant = None

    while True:
        try:
            finish(job, exit_code)
            return
        except psycopg.OperationalError:
            logging.exception("Unable to record workflow outcome, retrying")
            time.sleep(5)


def main() -> None:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    while True:
        try:
            job = claim()
        except psycopg.OperationalError:
            logging.exception("Unable to query daily jobs")
            job = None
        if job:
            run_job(job)
        else:
            time.sleep(5)


if __name__ == "__main__":
    main()
