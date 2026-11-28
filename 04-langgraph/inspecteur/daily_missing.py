# =====================================================================
# Job quotidien « offres en cours absentes de la base ».
#
# Enchaîne, dans l'ordre voulu par le RÉGISSEUR :
#   1. scrape portail (AO + consultations) et bons de commande, import DB ;
#   2. marche du listing + audit des références absentes (deadline live) ;
#   3. téléchargement des dossiers / documents des NOUVELLES offres ;
#   4. extraction CPS/champs riches + enrichissement de `tenders`.
#
# Aucune suppression de ZIP ni de tender : uniquement des upserts.
# =====================================================================
from __future__ import annotations

import json
from datetime import date
from typing import Any


def _nettoyer(valeur: dict[str, Any]) -> dict[str, Any]:
    """JSON-safe pour les résumés de logs."""
    return json.loads(json.dumps(valeur, ensure_ascii=False, default=str))


def run(
    *,
    company_id: str = "EXPLEO-IT-001",
    collect_date: str | None = None,
    scratch_minutes: float = 45,
    walk_minutes: float = 30,
    docs_minutes: float = 240,
    workers: int = 6,
    skip_scrape: bool = False,
    skip_audit: bool = False,
    skip_documents: bool = False,
) -> dict[str, Any]:
    from . import (collect_documents, config, cps_docs, db, enrich_tender_documents,
                   offers_audit, offers_walk, scrape_bdc, scrape_portal)

    jour = collect_date or date.today().isoformat()
    resultats: dict[str, Any] = {
        "date": jour, "company_id": company_id, "scrape": {}, "audit": {},
        "documents": {}, "champs": {}, "enrichissement": {},
    }

    # 1) Offres « en cours » du portail et des bons de commande.
    #    import_to_db / collect_purchase_notices filtrent déjà les deadlines
    #    passées et posent offer_type (migration 015).
    if not skip_scrape:
        print("[daily-missing] 1) scrape portail + bons de commande", flush=True)
        items = scrape_portal.scrape_incremental(per_term=60, workers=workers)
        resultats["scrape"]["portail"] = scrape_portal.import_to_db(items, jour)
        resultats["scrape"]["portail"]["offres_vues"] = len(items)
        resultats["scrape"]["bdc"] = scrape_bdc.collect_purchase_notices(jour, workers)
    else:
        resultats["scrape"] = {"ignore": True}

    # 2) Nouvelle marche du listing (audit_map frais) puis audit des absentes.
    #    Sans cette marche, l'audit pourrait rejouer une map périmée.
    if not skip_audit:
        print("[daily-missing] 2) marche listing + audit des absentes", flush=True)
        resultats["audit"]["walk"] = offers_walk.walk(
            minutes=walk_minutes, audit_map=True)
        resultats["audit"]["absentes"] = offers_audit.audit(
            minutes=scratch_minutes, workers=workers)
    else:
        resultats["audit"] = {"ignore": True}

    # 3) Dossiers/ZIP des nouvelles offres -> cps_documents/tender_documents.
    if not skip_documents:
        print("[daily-missing] 3) documents des nouvelles offres", flush=True)
        resultats["documents"]["portail_cps"] = cps_docs.collect_docs(
            minutes=min(docs_minutes, 60), limit=2000,
            store_originals=None, fallback=True)
        resultats["documents"]["dce"] = collect_documents.run_documents(
            jour, company_id, workers=workers,
            time_budget=docs_minutes, all_tenders=True)
        resultats["champs"] = cps_docs.extract_all_fields(
            minutes=min(docs_minutes, 60))
        resultats["enrichissement"] = enrich_tender_documents.refresh_open_tenders(
            workers, jour)
    else:
        resultats["documents"] = {"ignore": True}

    db.close()
    return _nettoyer(resultats)
