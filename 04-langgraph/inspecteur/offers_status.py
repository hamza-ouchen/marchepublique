# =====================================================================
# Statut RÉEL des consultations depuis leur page de détail portail.
#
# Le portail garde en ligne les consultations terminées : la liste ne
# permet pas de distinguer « en cours » / « clôturée » (la date affichée
# est une fin d'affichage). SEULE la page de détail fait foi :
#   • « Date et heure limite de remise des plis : <date> » -> offre
#     OUVERTE : date_remise mise à jour (offre supprimée si déjà passée) ;
#   • label sans valeur / absent -> consultation TERMINÉE : SUPPRESSION
#     (scores/verdicts d'abord — FK sans cascade — puis documents en
#     cascade via tender_documents).
#
# Idempotent : ne traite que les offres ouvertes à date_remise NULL ; une
# erreur HTTP laisse la ligne intacte (retraitée au prochain cycle).
# =====================================================================
from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from typing import Any

import requests

from . import config, db

_DEADLINE_BLOCK_RE = re.compile(
    r"Date\s+et\s+heure\s+limite\s+de\s+remise\s+des\s+plis\s*:?", re.I)
_DATE_VALUE_RE = re.compile(
    r"(?:Lun|Mar|Mer|Jeu|Ven|Sam|Dim)\s+(\d{1,2})\s+"
    r"([A-Za-zÀ-ÿ]{3,5})\.?\s+(\d{4})\s+(\d{1,2}:\d{2})")
MONTHS_FR = {
    "janv": 1, "fevr": 2, "févr": 2, "mars": 3, "avr": 4, "mai": 5, "juin": 6,
    "juil": 7, "aout": 8, "août": 8, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
    "déc": 12,
}
_tls: dict[str, Any] = {}


def _session() -> requests.Session:
    if "s" not in _tls:
        s = requests.Session()
        s.headers.update({"User-Agent": config.USER_AGENT})
        _tls["s"] = s
    return _tls["s"]


def parse_deadline_value(detail_html: str) -> date | None:
    """Date limite réelle si présente, sinon None (consultation terminée)."""
    text = re.sub(r"<[^>]+>", " ", detail_html)
    text = re.sub(r"\s+", " ", text)
    m = _DEADLINE_BLOCK_RE.search(text)
    if not m:
        return None
    dm = _DATE_VALUE_RE.search(text[m.end():m.end() + 80])
    if not dm:
        return None
    key = dm.group(2).lower()[:4]
    key = re.sub(r"[^a-z]", "", key)
    month = MONTHS_FR.get(key)
    if not month:
        return None
    try:
        return date(int(dm.group(3)), month, int(dm.group(1)))
    except ValueError:
        return None


def refresh_one(tender: dict[str, Any], today: date) -> dict[str, Any]:
    """Rafraîchit UNE offre depuis sa page de détail. Ne lève pas."""
    ref = tender.get("reference") or ""
    url = tender.get("source_url") or ""
    if "refConsultation" not in url:
        return {"reference": ref, "status": "skipped", "reason": "no_detail_url"}
    try:
        r = _session().get(url, timeout=config.REQUEST_TIMEOUT_S)
    except requests.RequestException as exc:
        return {"reference": ref, "status": "error", "reason": str(exc)[:100]}
    if r.status_code != 200:
        return {"reference": ref, "status": "error", "reason": f"http {r.status_code}"}
    dl = parse_deadline_value(r.text)
    if dl is None or dl < today:
        if config.DELETE_FINISHED_OFFERS:
            db.delete_offer(ref)
            return {"reference": ref, "status": "deleted",
                    "reason": None if dl is None else f"deadline passee {dl}"}
        return {"reference": ref, "status": "dead_kept", "reason": str(dl)}
    db.set_tender_deadline(ref, dl)
    return {"reference": ref, "status": "ouvert", "deadline": str(dl)}


def refresh(minutes: float | None = None, workers: int | None = None,
            limit: int = 100000) -> dict[str, int]:
    """Rafraîchit toutes les offres ouvertes à date_remise NULL."""
    minutes = minutes if minutes is not None else config.AUDIT_MINUTES
    workers = workers or config.AUDIT_WORKERS
    today = date.today()
    tenders = db.tenders_missing_deadline(limit)
    print(f"[status] {len(tenders)} offre(s) à rafraîchir", flush=True)
    stats: dict[str, int] = {"ouvert": 0, "deleted": 0, "error": 0, "skipped": 0}
    t0 = time.monotonic()
    batch = max(workers * 4, 16)
    for i in range(0, len(tenders), batch):
        if time.monotonic() - t0 > minutes * 60.0:
            print("[status] budget atteint, arrêt propre", flush=True)
            break
        chunk = tenders[i:i + batch]
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(refresh_one, t, today): t for t in chunk}
            for fut in as_completed(futs):
                try:
                    res = fut.result()
                except Exception as exc:
                    res = {"reference": futs[fut].get("reference", "?"),
                           "status": "error", "reason": str(exc)[:100]}
                stats[res["status"]] = stats.get(res["status"], 0) + 1
        print(f"[status] {sum(stats.values())}/{len(tenders)} | "
              f"{stats} ({time.monotonic()-t0:.0f}s)", flush=True)
    return stats
