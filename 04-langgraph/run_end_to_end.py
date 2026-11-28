# =====================================================================
# SOU9NA — exécution bout-en-bout (local, sans push).
#   1. JUGE (LangGraph) -> verdicts
#   2. COMPAGNON compose_digest -> digests
#   3. COMPAGNON distribuer -> MCP canaux (email + WhatsApp)
#   4. Contrôle INSPECTEUR (idempotence sur un PDF de fixture)
# =====================================================================
from __future__ import annotations

import json
import os
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "04-langgraph" / "juge"))
sys.path.insert(0, str(ROOT / "03-agentic-ai" / "compagnon"))
sys.path.insert(0, str(ROOT / "04-langgraph" / "inspecteur"))

# charge .env
envpath = ROOT / "02-backend" / ".env"
for line in envpath.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if line and not line.startswith("#") and "=" in line:
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

import graph as juge_graph
import compose_digest
import distribuer
import cps_ingest


def main() -> None:
    d = sys.argv[1] if len(sys.argv) > 1 else date.today().isoformat()
    print(f"=== RUN {d} ===")

    # 1. JUGE via LangGraph
    print("\n[1/4] JUGE (LangGraph) ...")
    rapport_juge = juge_graph.run(d)
    print(json.dumps(rapport_juge, ensure_ascii=False))

    # 2. Composition du digest
    print("\n[2/4] COMPAGNON compose_digest ...")
    rapport_compose = compose_digest.composer(d)
    print(json.dumps(rapport_compose, ensure_ascii=False))

    # 3. Distribution via MCP canaux
    print("\n[3/4] COMPAGNON distribuer ...")
    rapport_dist = distribuer.distribuer(d)
    print(json.dumps(rapport_dist, ensure_ascii=False))

    # 4. Contrôle INSPECTEUR (idempotence)
    print("\n[4/4] INSPECTEUR idempotence (PDF fixture) ...")
    pdf = (ROOT / "02-backend" / "fixtures" / "cps" / "pdfs" / "2026-DTR-0123" / "cps.pdf").read_bytes()
    r1 = cps_ingest.ingest_cps("2026/DTR/0123", pdf, filename="cps.pdf")
    r2 = cps_ingest.ingest_cps("2026/DTR/0123", pdf, filename="cps.pdf")
    print("1er passage:", r1.get("status"), "| 2e passage:", r2.get("status"), r2.get("reason"))

    print("\n=== FIN ===")


if __name__ == "__main__":
    main()
