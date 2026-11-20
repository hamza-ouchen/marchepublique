"""Contrôle optionnel réel : lecture de six questions, sans génération juridique."""

import json
import sys
from pathlib import Path

from sou9na_rag.graphs import build_retrieve_graph
from sou9na_rag.store import AstraStore, Settings


def main() -> int:
    """Écrit un rapport sans jeton ni données d'autres corpus."""
    sys.stdout.reconfigure(encoding="utf-8")
    root = Path(__file__).parent
    questions = json.loads((root / "evaluations/smoke_questions.json").read_text(encoding="utf-8"))
    store = AstraStore(Settings.from_env())
    store.inspect()
    manifest = store.resolve_manifest()
    graph = build_retrieve_graph(store)
    results = []
    for item in questions:
        result = graph.invoke(
            {"query": item["query"], "top_k": 5, "document_sha256": manifest["document_sha256"]}
        )
        blocks = [passage["bloc"] for passage in result["passages"]]
        results.append(
            {
                **item,
                "status": result["status"],
                "returned_blocks": blocks,
                "found_in_top5": item["expected_block"] in blocks,
                "all_citations_present": all(
                    p["source_id"] and p["pages"] and p["document_sha256"]
                    for p in result["passages"]
                ),
            }
        )
    report = {
        "scope": "six French smoke queries, not a production quality benchmark",
        "document_sha256": manifest["document_sha256"],
        "hits_at_5": sum(item["found_in_top5"] for item in results),
        "total": len(results),
        "results": results,
    }
    path = root / "artifacts/live-search-report.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["hits_at_5"] == len(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
