"""Commandes locales d'inspection, préparation, ingestion et recherche."""

import argparse
import json
import sys
from pathlib import Path

from .documents import CORPUS, DocumentError, extract_pdf, make_chunks
from .graphs import build_ingest_graph, build_retrieve_graph
from .store import AstraStore, BackendError, Settings


def main() -> int:
    """Émet seulement un résultat JSON ; aucun jeton ni état interne complet."""
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="RAG documentaire SOUKNA / Astra DB")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("inspect")
    for command in ("prepare", "ingest"):
        sub = commands.add_parser(command)
        sub.add_argument("pdf")
        sub.add_argument("--expected-questions", type=int, default=125)
        if command == "prepare":
            sub.add_argument("--output", required=True)
    query = commands.add_parser("query")
    query.add_argument("text")
    query.add_argument("--top-k", type=int, default=5)
    query.add_argument("--document-sha256")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            extracted = extract_pdf(args.pdf)
            chunks = make_chunks(extracted, args.expected_questions)
            destination = Path(args.output)
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_text(
                "\n".join(json.dumps(c, ensure_ascii=False) for c in chunks) + "\n",
                encoding="utf-8",
            )
            result = {
                "status": "prepared",
                "pages": extracted["page_count"],
                "document_sha256": extracted["document_sha256"],
                "chunks": len(chunks),
            }
        else:
            store = AstraStore(Settings.from_env())
            if args.command == "inspect":
                result = store.inspect()
            elif args.command == "ingest":
                state = build_ingest_graph(store).invoke(
                    {"path": args.pdf, "expected_questions": args.expected_questions}
                )
                result = {
                    key: state[key]
                    for key in ("status", "error", "inserted", "skipped", "manifest")
                    if key in state
                }
            else:
                state = build_retrieve_graph(store).invoke(
                    {
                        "query": args.text,
                        "top_k": args.top_k,
                        "corpus": CORPUS,
                        **(
                            {"document_sha256": args.document_sha256}
                            if args.document_sha256
                            else {}
                        ),
                    }
                )
                result = {
                    key: state[key]
                    for key in ("status", "error", "occurrences", "passages")
                    if key in state
                }
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get("error") else 0
    except (BackendError, DocumentError, ValueError, OSError) as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
