"""Le jeu PDF ne doit jamais être présenté comme une validation réglementaire."""

import json
from pathlib import Path

from evaluate_golden import evaluate


def test_dataset_has_50_distinct_sourced_questions():
    dataset = json.loads(
        (Path(__file__).resolve().parents[2] / "golden-set.json").read_text(encoding="utf-8")
    )
    assert len(dataset["questions"]) == 50
    assert len({q["expected_article"] for q in dataset["questions"]}) == 50
    assert dataset["independent_legal_validation"] is False
    assert all(
        q["ask"] and q["corpus"] == "faq" and q["expected_source"] for q in dataset["questions"]
    )


def test_evaluator_does_not_count_wrong_source_or_backend_error_as_success():
    dataset = {
        "kind": "test",
        "questions": [
            {
                "ask": "question",
                "corpus": "faq",
                "expected_source": "right",
                "expected_article": "Q-001",
            }
        ]
        * 50,
    }

    def wrong_source(*args):
        return {"passages": [{"source": "wrong", "article": "Q-001"}]}

    assert evaluate(dataset, wrong_source)["recall_at_5"] == 0

    def unavailable(*args):
        return {"passages": [], "erreur": "rag_indisponible"}

    assert not evaluate(dataset, unavailable)["passed"]
