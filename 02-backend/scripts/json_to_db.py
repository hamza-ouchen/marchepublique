# =====================================================================
# json_to_db.py — Importe un fichier JSON PROPRE (produit par
# scrape_to_json.py) dans la table Supabase 'tenders' (upsert par
# reference). Aucun scraping ici : on ne lit que le JSON.
#
# Usage :
#   python scripts/json_to_db.py                      # <- offers_clean.json
#   python scripts/json_to_db.py --in foo.json
#   python scripts/json_to_db.py --dry-run
# =====================================================================
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass

import psycopg
from soukna_graph import config


def to_date(v):
    if v is None:
        return None
    if isinstance(v, date):
        return v
    try:
        return date.fromisoformat(str(v)[:10])
    except ValueError:
        return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--in", dest="inp", default="offers_clean.json")
    ap.add_argument("--db-url", dest="db_url", default=None,
                    help="Override DATABASE_URL (Supabase connection string).")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    in_path = Path(args.inp)
    if not in_path.is_absolute():
        in_path = Path(__file__).resolve().parent.parent / in_path
    if not in_path.exists():
        print(f"ERROR: file not found: {in_path}", file=sys.stderr)
        return 1

    with in_path.open(encoding="utf-8") as f:
        records = json.load(f)
    print(f"Loaded {len(records)} records from {in_path}", flush=True)

    if args.dry_run:
        print("Dry run: no DB writes.")
        return 0

    url = args.db_url or os.getenv("DATABASE_URL") or config.DATABASE_URL
    if not url or "xxxx" in url:
        print("ERROR: DATABASE_URL not set (or placeholder).", file=sys.stderr)
        return 1

    conn = psycopg.connect(url)
    conn.autocommit = False
    inserted = updated = failed = 0
    errors = []
    for idx, r in enumerate(records):
        try:
            conn.execute(
                """
                INSERT INTO tenders (reference, organisme, objet, secteur, region,
                                     montant_mad, caution_mad, lots, qualifications_exigees,
                                     delai_jours, date_publication, date_remise, date_collecte,
                                     statut, source, source_url, cree_le, mis_a_jour_le)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,now(),NULL)
                ON CONFLICT (reference) DO UPDATE SET
                    organisme=EXCLUDED.organisme, objet=EXCLUDED.objet, secteur=EXCLUDED.secteur,
                    region=EXCLUDED.region, montant_mad=EXCLUDED.montant_mad,
                    date_remise=EXCLUDED.date_remise, date_collecte=EXCLUDED.date_collecte,
                    statut=EXCLUDED.statut, source_url=EXCLUDED.source_url,
                    mis_a_jour_le=now()
                """,
                (r["reference"], r.get("organisme") or "Inconnu", r.get("objet"),
                 r.get("secteur") or "autre", r.get("region") or "autre",
                 r.get("montant_mad"), r.get("caution_mad"),
                 r.get("lots") or [], r.get("qualifications_exigees") or [],
                 r.get("delai_jours") or 0, to_date(r.get("date_publication")),
                 to_date(r.get("date_remise")), to_date(r.get("date_collecte")) or date.today(),
                 r.get("statut") or "ouvert", r.get("source") or "portail",
                 r.get("source_url")),
            )
            # psycopg rowcount not reliable for upsert; count as written
            inserted += 1
        except Exception as e:
            failed += 1
            errors.append((r.get("reference"), repr(e)))
            if failed <= 20:
                print(f"[ERR] {r.get('reference')}: {e}", flush=True)
        if (idx + 1) % 500 == 0:
            conn.commit()
            print(f"Committed up to {idx+1}. written={inserted} failed={failed}", flush=True)

    conn.commit()
    print(f"DONE. written={inserted} failed={failed} total={len(records)}", flush=True)
    if errors:
        print("First errors:", errors[:10], flush=True)
    conn.close()
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
PYEOF