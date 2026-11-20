"""50 questions réparties dans le PDF : jeu de non-régression, pas validation juridique."""

import argparse
import json
import re
from pathlib import Path

from sou9na_rag.documents import extract_pdf, make_chunks


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    extracted = extract_pdf(args.pdf)
    chunks = make_chunks(extracted)
    unique = {c["block_id"]: c for c in chunks if c["content_type"] == "qa"}
    selected = list(unique)[::2][:50]
    questions = []
    for block in selected:
        text = unique[block]["text"].splitlines()[0]
        question = re.sub(r"^\[Q-\d{3}\]\s*", "", text).strip()
        questions.append(
            {
                "ask": question,
                "corpus": "faq",
                "expected_article": block,
                "expected_source": extracted["document"],
            }
        )
    dataset = {
        "kind": "reference_pdf_smoke",
        "independent_legal_validation": False,
        "document_sha256": extracted["document_sha256"],
        "questions": questions,
    }
    Path(args.output).write_text(
        json.dumps(dataset, ensure_ascii=False, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()
