# =====================================================================
# INSPECTEUR — serveur A2A (port 8101)
# Responsable de TOUTE la donnée d'entrée :
#   1. avis du portail -> public.tenders  (via scrape_portal)
#   2. PDF/DCE/CPS      -> tender_documents + cps_sections
#      (outil Python interne collect_documents, PAS un autre agent)
# Le RÉGISSEUR l'appelle en JSON-RPC `message/send` + X-Internal-Token.
# =====================================================================
from __future__ import annotations

import logging
import os
import sys
from datetime import datetime
from pathlib import Path
try:
    import sys as _sys
    _sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    _sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

_RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_RACINE / "04-langgraph"))
sys.path.insert(0, str(_RACINE / "04-langgraph" / "inspecteur"))

from a2a_env import charger_env  # noqa: E402

charger_env()

import collect_documents  # noqa: E402
import db_cps  # noqa: E402
from enrich_tender_documents import process_stored_tenders, refresh_open_tenders, run_ao_fallback  # noqa: E402
from scrape_bdc import collect_purchase_notices  # noqa: E402
import scrape_portal  # noqa: E402
from a2a_agent import creer_app  # noqa: E402


def _collecte_avis(donnees: dict) -> dict:
    date = donnees["date"]
    mode = donnees.get("mode", "portail")
    if mode not in ("portail", "secours", "backfill"):
        mode = "portail"

    collecte = donnees.get("collecte", "auto")
    inseres = 0
    motif_repli = None
    if collecte == "none":
        items, source = [], "aucune"
    elif mode == "secours":
        items, source = [], "secours"
    else:
        try:
            if mode == "backfill" or not list(scrape_portal.CHECKPOINT_DIR.glob("*.json")):
                cible = int(os.getenv("SCRAPE_TARGET", "6000"))
                items = scrape_portal.scrape_full(cible, 6, 40)
            else:
                items = scrape_portal.scrape_incremental(60, 6)
            inseres = scrape_portal.import_to_db(items, date) if items else 0
            source = "portail"
        except Exception as erreur_portail:                       # noqa: BLE001
            motif_repli = str(erreur_portail)[:300]
            logging.warning("Portail indisponible (%s) — aucune nouvelle collecte", motif_repli)
            items, source = [], "secours"

    if collecte != "none":
        etat = scrape_portal.load_state()
        etat.update({"last_scrape": datetime.now().isoformat(),
                     "last_mode": source, "last_count": len(items)})
        scrape_portal.save_state(etat)

    bons_de_commande = {"status": "skipped"}
    if collecte != "none" and mode != "secours":
        try:
            bons_de_commande = collect_purchase_notices(date, int(os.getenv("DOCUMENT_WORKERS", "8")))
        except Exception as exc:
            logging.warning("Collecte des bons de commande indisponible (%s)", type(exc).__name__)
            bons_de_commande = {"status": "unavailable", "error": type(exc).__name__}

    rapport = {
        "avis_nouveaux": inseres + bons_de_commande.get("imported", 0),
        "avis_lus": len(items) + bons_de_commande.get("new", 0),
        "doublons": max(0, len(items) - inseres),
        "rejetes": 0,
        "source": source,
        "avis_recycles": 0,
        "secours_raison": motif_repli,
        "bons_de_commande": bons_de_commande,
        "request_id": donnees.get("request_id"),
        # Compétence documentaire dédiée, appelée avant le scoring.
        "documents_differe": True,
    }
    return rapport


def _collecter_documents(donnees: dict) -> dict:
    """Collecte et enrichit les documents avant le calcul des scores."""
    date = donnees["date"]
    company = donnees.get("company_id") or os.environ["SOU9NA_CRON_COMPANY"]
    workers = max(1, int(os.getenv("DOCUMENT_WORKERS", "8")))
    if donnees.get("collecte") == "none":
        return {"source_documents": "stockage", "documents_ingerees": 0,
                "documents_annonces": 0, "annonces_enrichies": refresh_open_tenders(workers, date),
                "request_id": donnees.get("request_id")}
    rapport = collect_documents.run_documents(
        date, company,
        workers=workers, all_tenders=True, batch_size=workers * 2,
        time_budget=float(os.getenv("DOCUMENT_PORTAL_SECONDS", "540")),
    )
    if rapport["source_documents"] == "storage_indisponible":
        raise RuntimeError("Supabase Storage indisponible pour la collecte documentaire")
    rapport["ao_maroc"] = run_ao_fallback(
        date, float(os.getenv("DOCUMENT_FALLBACK_SECONDS", "240")),
        portal_unavailable=rapport["source_documents"] == "portail_indisponible",
    )
    rapport["stockage"] = process_stored_tenders(
        min(workers, 2), date, float(os.getenv("DOCUMENT_STORED_SECONDS", "120"))
    )
    rapport["annonces_enrichies"] = refresh_open_tenders(workers, date)
    rapport["request_id"] = donnees.get("request_id")
    return rapport


app = creer_app(
    "INSPECTEUR",
    {"collecte_avis": _collecte_avis, "collecter_documents": _collecter_documents},
    "Collecte des avis (tenders) puis, avant scoring, de leurs documents PDF "
    "(tender_documents). Seul agent autorisé sur le portail.",
)
