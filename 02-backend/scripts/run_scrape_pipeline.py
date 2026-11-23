# =====================================================================
# run_scrape_pipeline.py — Pipeline complet : scrape -> JSON propre ->
# import DB. Équivalent à lancer scrape_to_json puis json_to_db.
#
# Usage :
#   python scripts/run_scrape_pipeline.py
#   python scripts/run_scrape_pipeline.py --max-pages 100 --out offers.json
# =====================================================================
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="offers_clean.json")
    ap.add_argument("--max-pages", type=int, default=622)
    ap.add_argument("--db-url", dest="db_url", default=None)
    ap.add_argument("--skip-scrape", action="store_true",
                    help="Ne rescrape pas, importe le JSON existant.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    py = sys.executable
    if not args.skip_scrape:
        r = subprocess.run([py, str(HERE / "scrape_to_json.py"),
                            "--out", args.out, "--max-pages", str(args.max_pages)],
                           check=False)
        if r.returncode != 0:
            print("Scrape step failed.", file=sys.stderr)
            return r.returncode

    cmd = [py, str(HERE / "json_to_db.py"), "--in", args.out]
    if args.db_url:
        cmd += ["--db-url", args.db_url]
    if args.dry_run:
        cmd.append("--dry-run")
    r = subprocess.run(cmd, check=False)
    return r.returncode


if __name__ == "__main__":
    sys.exit(main())
PYEOF