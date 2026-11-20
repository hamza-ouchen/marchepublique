"""Évaluation réseau explicite : Recall@5, absence de citation et indisponibilité."""

import argparse
import json
from pathlib import Path

from sou9na_rag.project_service import chercher_projet


def evaluate(dataset, search=chercher_projet):
    results = []
    for q in dataset["questions"]:
        response = search(q["ask"], q["corpus"], 5)
        hit = any(
            p["source"] == q["expected_source"] and p["article"] == q["expected_article"]
            for p in response["passages"]
        )
        results.append(
            {
                "expected_article": q["expected_article"],
                "hit": hit,
                "error": response.get("erreur"),
                "passages": len(response["passages"]),
            }
        )
    recall = sum(r["hit"] for r in results) / len(results) if results else 0
    return {
        "questions": len(results),
        "recall_at_5": recall,
        "passed": len(results) == 50 and recall >= 0.8 and not any(r["error"] for r in results),
        "kind": dataset["kind"],
        "results": results,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="../golden-set.json")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    dataset = json.loads(Path(args.dataset).read_text(encoding="utf-8"))
    result = evaluate(dataset)
    destination = Path(args.report)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "results"}))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
