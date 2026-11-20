"""CLI d'exploitation : ingestion CPS par lot, corpus validé et recherche MCP."""

import argparse
import json
import sys
from pathlib import Path

from .cps import ingest_cps
from .postgres import CpsRepository
from .project_service import chercher_projet
from .project_store import ProjectStore
from .regulatory import ingest_regulatory
from .store import BackendError, Settings


def main():
    parser = argparse.ArgumentParser(description="SOU9NA — ingestion et recherche projet")
    sub = parser.add_subparsers(dest="command", required=True)
    cps = sub.add_parser("cps")
    cps.add_argument("--document-id", type=int)
    cps.add_argument("--limit", type=int, default=100)
    cps.add_argument("--report", required=True)
    reg = sub.add_parser("reglementation")
    reg.add_argument("manifest")
    reg.add_argument("--report", required=True)
    query = sub.add_parser("chercher")
    query.add_argument("requete")
    query.add_argument("--corpus", default="faq")
    query.add_argument("--nombre", type=int, default=5)
    args = parser.parse_args()
    try:
        store = ProjectStore(Settings.from_env())
        if args.command == "cps":
            repo = CpsRepository()
            ids = [args.document_id] if args.document_id is not None else repo.pending(args.limit)
            results = []
            for document_id in ids:
                try:
                    results.append(ingest_cps(repo, store, document_id))
                except BackendError as exc:
                    results.append(
                        {"document_id": document_id, "status": "failed", "error": str(exc)}
                    )
            result = {
                "status": "failed"
                if any(r["status"] == "failed" for r in results)
                else "completed",
                "documents": results,
            }
        elif args.command == "reglementation":
            result = ingest_regulatory(args.manifest, store, CpsRepository())
        else:
            result = chercher_projet(args.requete, args.corpus, args.nombre, store=store)
        code = 1 if result.get("erreur") or result.get("status") == "failed" else 0
    except Exception:
        # Une erreur réseau peut inclure DSN, en-têtes ou contenu : ne jamais l'afficher.
        result, code = {"status": "failed", "error": "RAG_OPERATION_FAILED"}, 1
    if getattr(args, "report", None):
        destination = Path(args.report)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
