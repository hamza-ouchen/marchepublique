# =====================================================================
# Audit live des offres absentes de la base — dresse la liste des
# références collectées (audit_map.jsonl) mais ABSENTES de 'tenders'
# (supprimées comme terminées, ou jamais scrapées) et vérifie chacune
# sur sa page de détail portail :
#   • « Date et heure limite de remise des plis » datée dans le futur
#     -> RE-INSERTION immédiate (offre réellement ouverte) ;
#   • sinon -> absence confirmée (compteur).
# C'est le contre-résumé définitif de « supprimée à tort ? » et
# « offre manquée ? » : le portail tranche lui-même.
# =====================================================================
from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any

import requests

from . import config, db, offers_status, offers_walk


def load_map() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    try:
        with config.AUDIT_MAP_PATH.open(encoding="utf-8") as f:
            for line in f:
                try:
                    it = json_item(line)
                    ref = it.get("reference") or ""
                    if ref:
                        out[ref] = it
                except Exception:
                    continue
    except FileNotFoundError:
        pass
    return out


def json_item(line: str) -> dict[str, Any]:
    import json
    return json.loads(line)


def audit(minutes: float | None = None, workers: int | None = None,
          limit: int = 100000) -> dict[str, int]:
    minutes = minutes if minutes is not None else config.AUDIT_MINUTES
    workers = workers or config.AUDIT_WORKERS
    mapped = load_map()
    print(f"[audit] {len(mapped)} références mappées", flush=True)
    current = {r["reference"] for r in db.query(
        "SELECT reference FROM tenders LIMIT 100000")}
    targets = [ref for ref, it in mapped.items()
               if ref not in current and it.get("url")][:limit]
    print(f"[audit] {len(targets)} absente(s) à auditer", flush=True)

    today = date.today()
    stats: dict[str, int] = {"reinserted": 0, "dead": 0, "error": 0,
                             "no_url": 0}
    t0 = time.monotonic()

    def check_one(ref: str, item: dict[str, Any]) -> dict[str, Any]:
        url = item.get("url") or ""
        try:
            r = offers_status._session().get(
                url, timeout=config.REQUEST_TIMEOUT_S)
        except requests.RequestException as exc:
            return {"reference": ref, "status": "error",
                    "reason": str(exc)[:100]}
        if r.status_code != 200:
            return {"reference": ref, "status": "error",
                    "reason": f"http {r.status_code}"}
        dl = offers_status.parse_deadline_value(r.text)
        if dl is None or dl < today:
            return {"reference": ref, "status": "dead",
                    "reason": None if dl is None else str(dl)}
        try:
            db.upsert_offer(
                reference=ref,
                organisme=offers_walk.clean_text(item.get("buyer"), 180)
                or "Inconnu",
                objet=offers_walk.clean_text(item.get("title"))
                or f"Consultation {ref}",
                secteur=offers_walk._sector_from_title(item.get("title") or "")
                or "autre",
                region=offers_walk.clean_text(item.get("city"), 120) or "autre",
                montant_mad=offers_walk.parse_amount(item.get("amount")),
                date_remise=dl, date_collecte=today, statut="ouvert",
                source_url=url[:2000])
            return {"reference": ref, "status": "reinserted", "deadline": str(dl)}
        except Exception as exc:
            return {"reference": ref, "status": "error", "reason": str(exc)[:150]}

    done = 0
    batch = max(workers * 4, 16)
    for i in range(0, len(targets), batch):
        if time.monotonic() - t0 > minutes * 60.0:
            print("[audit] budget atteint, arrêt propre", flush=True)
            break
        chunk = targets[i:i + batch]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(check_one, ref, mapped[ref]): ref
                    for ref in chunk}
            for fut in as_completed(futs):
                try:
                    res = fut.result()
                except Exception as exc:
                    res = {"reference": futs[fut], "status": "error",
                           "reason": str(exc)[:100]}
                stats[res["status"]] = stats.get(res["status"], 0) + 1
                if res["status"] == "reinserted":
                    print(f"[audit] ++ RE-INSERTED {res['reference']} "
                          f"(deadline {res.get('deadline')})", flush=True)
                done += 1
        print(f"[audit] {done}/{len(targets)} | {stats} "
              f"({time.monotonic()-t0:.0f}s)", flush=True)
    return stats
