# =====================================================================
# SOU9NA — Pipeline quotidien complet (LEGACY / secours manuel uniquement)
# Le chemin de production est désormais :
#   cron -> FastAPI (/cron/run) -> daily_worker -> RÉGISSEUR A2A ->
#   INSPECTEUR A2A -> COMPAGNON A2A -> JUGE A2A -> RÉGISSEUR (clôture).
# Ce runner reste disponible pour rejouer une chaîne localement sans A2A.
#   1. INSPECTEUR  : scrape AO en cours (déjà lancé à 07:30 via tâche planifiée)
#   2. COMPAGNON   : score via le moteur local utilisé par COMPAGNON A2A.
#   3. JUGE        : verdicts GO / A_ETUDIER / NO_GO
#   4. COMPAGNON   : compose_digest (FR + AR)
#   5. COMPAGNON   : distribuer via MCP canaux (email uniquement)
#
# Le scrape est indépendant (voir scrape_portal.py / run_daily_scrape.bat).
# Ce runner suppose que les tenders du jour sont déjà en DB.
# =====================================================================
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
sys.path.insert(0, str(ROOT / "04-langgraph" / "juge"))
sys.path.insert(0, str(ROOT / "03-agentic-ai" / "compagnon"))

def step(name: str, cmd: list[str]) -> bool:
    print(f"\n=== {name} ===", flush=True)
    r = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    out = (r.stdout or "") + (r.stderr or "")
    print(out[-4000:] if len(out) > 4000 else out, flush=True)
    if r.returncode != 0:
        print(f"!! {name} a échoué (exit {r.returncode})", flush=True)
        return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description="Exécute le workflow quotidien Sou9na.")
    parser.add_argument("date", nargs="?", type=date.fromisoformat)
    parser.add_argument("company", nargs="?", default="EXPLEO-IT-001")
    parser.add_argument("--scrape", choices=["full", "incremental", "none"])
    parser.add_argument("--target", type=int, default=6000)
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--max-pages", type=int, default=40)
    parser.add_argument("--doc-limit", type=int, default=6000)
    parser.add_argument("--docs", action="store_true",
                        help="collecter les documents même sans scrape")
    args = parser.parse_args()
    d = (args.date or date.today()).isoformat()
    company = args.company
    envpath = ROOT / "02-backend" / ".env"
    if envpath.is_file():
        for line in envpath.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ.setdefault(key.strip(), value.strip())
    print(f"=== PIPELINE QUOTIDIEN {d} — {company} ===", flush=True)

    scrape_cmd = [PY, str(ROOT / "04-langgraph" / "inspecteur" / "scrape_portal.py"),
                  "--mode", args.scrape, "--collect-date", d,
                  "--workers", str(args.workers)]
    if args.scrape == "full":
        scrape_cmd += ["--target", str(args.target),
                       "--max-pages", str(args.max_pages)]
    if args.scrape in ("full", "incremental") and not step("1/5 INSPECTEUR collecte", scrape_cmd):
        return 1

    if not step("2/5 COMPAGNON score",
                [PY, str(ROOT / "03-agentic-ai" / "compagnon" / "score_local.py"),
                 "--company", company, "--date", d]):
        return 1

    doc_cmd = [PY, str(ROOT / "04-langgraph" / "inspecteur" / "collect_documents.py"),
               d, company, "--workers", str(min(args.workers, 8))]
    if args.scrape == "full":
        doc_cmd += ["--all", "--limit", str(args.doc_limit)]
    if args.docs and not step("INSPECTEUR documents", doc_cmd):
        return 1

    # 2. JUGE
    if not step("3/5 JUGE verdicts",
                [PY, str(ROOT / "04-langgraph" / "juge" / "juge.py"), d, company]):
        return 1

    # 3. Digest
    if not step("4/5 COMPAGNON compose_digest",
                [PY, "-c",
                 f"import sys; sys.path.insert(0, r'{ROOT / '03-agentic-ai' / 'compagnon'}'); "
                 "import compose_digest, json; print(json.dumps(compose_digest.composer(*sys.argv[1:]), ensure_ascii=False))",
                 d, company]):
        return 1

    # 4. Distribution (email uniquement — WhatsApp désactivé)
    if not step("5/5 COMPAGNON distribuer (email)",
                [PY, "-c",
                 f"import sys; sys.path.insert(0, r'{ROOT / '03-agentic-ai' / 'compagnon'}'); "
                 "import distribuer, json; result = distribuer.distribuer(*sys.argv[1:]); "
                 "print(json.dumps(result, ensure_ascii=False)); sys.exit(bool(result['echecs']))", d, company]):
        return 1

    print("\n=== PIPELINE TERMINÉ ===", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
