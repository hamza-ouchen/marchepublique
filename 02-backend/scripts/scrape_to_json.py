# =====================================================================
# scrape_to_json.py — Scrape le portail marchespublics.gov.ma (recherche
# avancée paginée) et écrit les résultats dans un fichier JSON PROPRE
# (normalisé), AVANT toute insertion en base. Permet de relire/valider
# les données avant l'import DB.
#
# Usage :
#   python scripts/scrape_to_json.py                 # -> offers_clean.json
#   python scripts/scrape_to_json.py --out foo.json
#   python scripts/scrape_to_json.py --max-pages 50
# =====================================================================
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.tools import portal

# Mapping ville -> région officielle (repli : on garde la ville si inconnue).
_CITY_TO_REGION = {
    "casablanca": "casa-settat", "mohammedia": "casa-settat", "settat": "casa-settat",
    "rabat": "rabat-sale-kenitra", "sale": "rabat-sale-kenitra", "kenitra": "rabat-sale-kenitra",
    "tanger": "tanger-tetouan-alhoceima", "tetouan": "tanger-tetouan-alhoceima",
    "agadir": "souss-massa", "marrakech": "marrakech-safi", "safi": "marrakech-safi",
    "fes": "fes-meknes", "meknes": "fes-meknes", "oujda": "oriental", "nador": "oriental",
    "agadir ida ou tanane": "souss-massa",
}


def parse_amount(txt):
    if not txt:
        return None
    s = str(txt).strip().replace(" ", "").replace("\u00a0", "").replace("\u202f", "")
    s = s.replace(",", ".")
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def clean_text(t, n=500):
    if t is None:
        return None
    t = str(t).strip()
    return t[:n] if t else None


def _normalize_region(city):
    if not city:
        return "autre"
    low = city.strip().lower()
    # Prendre le dernier token (ex. "Maroc Safi" -> "safi")
    token = low.split()[-1] if low.split() else low
    return _CITY_TO_REGION.get(token, _CITY_TO_REGION.get(low, low))


def normalize(item, today):
    ref = clean_text(item.get("source_ref"))
    if not ref:
        ref = None
    deadline = item.get("deadline")
    dl_date = None
    if deadline:
        try:
            dl_date = date.fromisoformat(str(deadline))
        except ValueError:
            dl_date = None
    delai = 0
    if dl_date:
        d = (dl_date - today).days
        delai = d if d >= 0 else 0
    city = clean_text(item.get("city"))
    # Secteur : déduit du titre si le portail ne le fournit pas.
    secteur = clean_text(item.get("sector"))
    if not secteur or secteur.lower() == "autre":
        secteur = portal._sector_from_title(item.get("title") or "")
    if not secteur:
        secteur = "autre"
    # Statut selon l'échéance.
    if dl_date is not None and dl_date < today:
        statut = "clos"
    else:
        statut = "ouvert"
    return {
        "reference": ref,
        "organisme": clean_text(item.get("buyer")) or "Inconnu",
        "objet": clean_text(item.get("title")),
        "secteur": secteur,
        "region": _normalize_region(city),
        "montant_mad": parse_amount(item.get("amount")),
        "caution_mad": None,
        "lots": [],
        "qualifications_exigees": [],
        "delai_jours": delai,
        "date_publication": None,
        "date_remise": dl_date.isoformat() if dl_date else None,
        "date_collecte": today.isoformat(),
        "statut": statut,
        "source": "portail",
        "source_url": clean_text(item.get("url"), 2000),
        "raw": item.get("raw") or {},
        "scraped_at": datetime.now(timezone.utc).isoformat(),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="offers_clean.json")
    ap.add_argument("--max-pages", type=int, default=622)
    args = ap.parse_args()

    today = date.today()
    print(f"Scraping (max_pages={args.max_pages})...", flush=True)
    t0 = time.time()

    def _progress(page, collected, new):
        if page % 10 == 0 or page == 1:
            print(f"  page {page}: collected={collected} new={new}", flush=True)

    items, stats = portal.advanced_search(max_pages=args.max_pages, progress_cb=_progress)
    print(f"Scraped {len(items)} unique items in {time.time()-t0:.1f}s", flush=True)

    clean = []
    skipped_closed = 0
    for it in items:
        n = normalize(it, today)
        if not n["reference"]:
            print(f"  [skip] item without reference: {it.get('title')}", flush=True)
            continue
        # Ne conserver que les consultations EN COURS (remise >= aujourd'hui).
        if n["statut"] != "ouvert":
            skipped_closed += 1
            continue
        clean.append(n)
    if skipped_closed:
        print(f"  [skip] {skipped_closed} consultation(s) cloturee(s) exclue(s).", flush=True)

    out_path = Path(args.out)
    if not out_path.is_absolute():
        out_path = Path(__file__).resolve().parent.parent / out_path
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(clean, f, ensure_ascii=False, indent=2, default=str)
    print(f"Wrote {len(clean)} clean records to {out_path}", flush=True)
    print(json.dumps({"pages": stats["pages"], "raw_items": stats["raw_items"],
                      "empty_pages": stats["empty_pages"], "unique": len(clean)},
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
PYEOF