# =====================================================================
# Pipeline complet en une commande (« full scraping in one row ») :
#   1) scrape des offres (scrape_to_json.py)
#   2) nettoyage / validation du JSON (références, plausibilité, dédup)
#   3) import en base (json_to_db.py)
#   4) collecte des documents CPS (inspecteur.cps_collect)
# =====================================================================
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
BACKEND = HERE.parents[1] / "02-backend"
SCRIPTS = BACKEND / "scripts"


def _run(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"\n>>> {' '.join(cmd)}", flush=True)
    r = subprocess.run(cmd, cwd=str(cwd or BACKEND))
    return r.returncode


def _clean_json(in_path: Path, out_path: Path) -> dict[str, int]:
    """Valide et nettoie le JSON scrappé avant insertion en base."""
    if not in_path.exists():
        raise FileNotFoundError(f"JSON introuvable : {in_path}")
    records = json.loads(in_path.read_text(encoding="utf-8"))
    seen: set[str] = set()
    clean: list[dict[str, Any]] = []
    dropped = {"sans_reference": 0, "montant_invalide": 0, "date_invalide": 0, "doublon": 0}
    for r in records:
        ref = (r.get("reference") or "").strip()
        if not ref:
            dropped["sans_reference"] += 1
            continue
        if ref in seen:
            dropped["doublon"] += 1
            continue
        seen.add(ref)
        # Plausibilité montant
        m = r.get("montant_mad")
        if m is not None:
            try:
                if float(m) <= 0:
                    r["montant_mad"] = None
            except (TypeError, ValueError):
                r["montant_mad"] = None
                dropped["montant_invalide"] += 1
        # Plausibilité dates
        dr = r.get("date_remise")
        dp = r.get("date_publication")
        if dr and dp:
            try:
                if date.fromisoformat(str(dr)[:10]) < date.fromisoformat(str(dp)[:10]):
                    r["date_remise"] = None
                    r["delai_jours"] = 0
                    dropped["date_invalide"] += 1
            except ValueError:
                pass
        # Normaliser les listes
        r["lots"] = r.get("lots") or []
        r["qualifications_exigees"] = r.get("qualifications_exigees") or []
        r["secteur"] = r.get("secteur") or "autre"
        r["region"] = r.get("region") or "autre"
        r["organisme"] = r.get("organisme") or "Inconnu"
        r["statut"] = r.get("statut") or "ouvert"
        clean.append(r)

    out_path.write_text(json.dumps(clean, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8")
    stats = {"total": len(records), "clean": len(clean), "dropped_total": len(records) - len(clean)}
    stats.update(dropped)
    print(f"[clean] {len(records)} -> {len(clean)} records "
          f"(dropped: {dropped})", flush=True)
    return stats


def run_full(args: Any) -> int:
    """Exécute le pipeline complet en une commande."""
    max_pages = getattr(args, "max_pages", None) or 622
    store_originals = getattr(args, "store_originals", False)
    out_json = BACKEND / "offers_clean.json"
    clean_json = BACKEND / "offers_clean_validated.json"

    t0 = time.time()

    # 1) Scrape
    rc = _run([sys.executable, str(SCRIPTS / "scrape_to_json.py"),
               "--out", str(out_json), "--max-pages", str(max_pages)],
              cwd=BACKEND)
    if rc != 0:
        print(f"[full] Échec du scrape (rc={rc}).", file=sys.stderr)
        return rc

    # 2) Nettoyage
    try:
        _clean_json(out_json, clean_json)
    except Exception as exc:
        print(f"[full] Échec du nettoyage : {exc}", file=sys.stderr)
        return 1

    # 3) Import en base
    rc = _run([sys.executable, str(SCRIPTS / "json_to_db.py"),
               "--in", str(clean_json)])
    if rc != 0:
        print(f"[full] Échec de l'import (rc={rc}).", file=sys.stderr)
        return rc

    # 4) Collecte des documents (inspecteur)
    from . import cps_collect
    os.environ.setdefault("ENV_FILE", str(BACKEND / ".env"))
    # re-import config with env file
    import importlib
    from . import config as _cfg
    importlib.reload(_cfg)
    stats = cps_collect.collect(
        dry_run=False,
        max_docs=getattr(args, "max_docs", None) or 1000,
        store_originals=store_originals,
        only_pertinent=True,
        limit=getattr(args, "limit", None) or 5000,
    )
    print("\n[full] Collecte documents :", flush=True)
    print(json.dumps(stats, ensure_ascii=False, indent=2, default=str))

    print(f"\n[full] Pipeline terminé en {time.time() - t0:.1f}s.")
    return 0


def run_full_job(args: Any) -> int:
    """Le job COMPLET de l'agent, dans l'ordre, tout idempotent :

      1) marche du listing portail (reprise sur état persisté) — offre
         à deadline passée : NON insérée ; portail fermé : jamais « done »
      2) statuts réels depuis les pages de détail (offres terminées
         supprimées avec scores/verdicts/documents)
      3) audit live des offres absentes de la base (ré-insertion des
         ouvertes)
      4) documents DCE (portail d'abord, aomaroc en repli) — ingestion
         totale, même texte insuffisant
      5) champs riches (montant/caution/lots/qualifications/délai)
    """
    from datetime import date
    from . import config, db, cps_docs, offers_audit, offers_status, offers_walk

    t0 = time.time()
    today = date.today()

    # 1) marche du listing (reprise / collecte audit-map)
    print("\n[full-job] 1) marche du listing portail", flush=True)
    walk_stats = offers_walk.walk(minutes=config.WALK_MINUTES,
                                  audit_map=True)
    print(json.dumps(walk_stats, ensure_ascii=False, indent=2, default=str))

    # 2) statuts réels (suppression des terminées)
    print("\n[full-job] 2) statuts réels (pages de détail)", flush=True)
    status_stats = offers_status.refresh(minutes=config.AUDIT_MINUTES,
                                         workers=config.AUDIT_WORKERS)
    print(json.dumps(status_stats, ensure_ascii=False, indent=2, default=str))

    # 3) audit des offres absentes (ré-insertion des ouvertes)
    print("\n[full-job] 3) audit des offres absentes", flush=True)
    audit_stats = offers_audit.audit(minutes=config.AUDIT_MINUTES,
                                     workers=config.AUDIT_WORKERS)
    print(json.dumps(audit_stats, ensure_ascii=False, indent=2, default=str))

    # 4) documents DCE (portail d'abord, aomaroc en repli)
    print("\n[full-job] 4) documents (portail, repli aomaroc)", flush=True)
    docs_stats = cps_docs.collect_docs(minutes=config.DOCS_MINUTES,
                                       store_originals=getattr(
                                           args, "store_originals", None))
    print(json.dumps(docs_stats, ensure_ascii=False, indent=2, default=str))

    # 5) champs riches depuis CPS/RC
    print("\n[full-job] 5) champs riches (CPS/RC)", flush=True)
    fields_stats = cps_docs.extract_all_fields(minutes=config.FIELDS_MINUTES)
    print(json.dumps(fields_stats, ensure_ascii=False, indent=2, default=str))

    db.close()
    print(f"\n[full-job] Job complet terminé en {time.time() - t0:.1f}s.")
    return 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(prog="inspecteur-full")
    ap.add_argument("--max-pages", type=int, default=622)
    ap.add_argument("--max-docs", type=int, default=1000)
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--store-originals", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    sys.exit(run_full(args))
