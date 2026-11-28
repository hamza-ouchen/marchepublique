"""Déclencheur quotidien Sou9na — remplace une cron line manuelle.

Le scheduler n'appelle jamais les agents : il POSTe uniquement /cron/run sur
FastAPI, qui met en file TOUTES les entreprises éligibles.
"""
from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

_ENV = Path(__file__).resolve().parent / ".env"
if _ENV.is_file():
    for _ligne in _ENV.read_text(encoding="utf-8-sig").splitlines():
        _ligne = _ligne.strip()
        if _ligne and not _ligne.startswith("#") and "=" in _ligne:
            _cle, _valeur = _ligne.split("=", 1)
            os.environ.setdefault(_cle.strip(), _valeur.strip())

SECRET = os.getenv("CRON_SECRET", "")
BASE = os.getenv("SOU9NA_API_URL", "http://127.0.0.1:8000").rstrip("/")
HEURE = os.getenv("SOU9NA_CRON_TIME", "07:35")
FUSEAU = os.getenv("SOU9NA_CRON_TZ", "Africa/Casablanca")
MODE = os.getenv("SOU9NA_CRON_MODE", "auto")


def prochaine_heure() -> datetime:
    fuseau = ZoneInfo(FUSEAU)
    hh, mm = (int(x) for x in HEURE.split(":")[:2])
    maintenant = datetime.now(fuseau)
    cible = maintenant.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if cible <= maintenant:
        cible += timedelta(days=1)
    return cible


def declencher() -> None:
    if not SECRET:
        print("CRON_SECRET manquant — déclenchement ignoré", file=sys.stderr)
        return
    requete = urllib.request.Request(
        f"{BASE}/cron/run?mode={MODE}",
        headers={"X-Cron-Secret": SECRET},
        method="POST",
    )
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            corps = json.loads(reponse.read().decode("utf-8"))
            print(f"cron ok — {corps.get('count', 0)} entreprise(s) en file")
    except urllib.error.HTTPError as err:
        print(f"cron HTTP {err.code}: {err.read().decode('utf-8', 'replace')}",
              file=sys.stderr)
    except Exception as err:  # noqa: BLE001
        print(f"cron erreur: {err}", file=sys.stderr)


def main() -> None:
    print(f"Scheduler Sou9na — {HEURE} {FUSEAU} -> {BASE}/cron/run", flush=True)
    while True:
        cible = prochaine_heure()
        attente = (cible - datetime.now(ZoneInfo(FUSEAU))).total_seconds()
        print(f"Prochain déclenchement: {cible.isoformat()}", flush=True)
        time.sleep(max(1, attente))
        declencher()
        time.sleep(60)  # évite un double déclenchement autour de minuit


if __name__ == "__main__":
    main()
