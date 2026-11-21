"""Authenticité du fichier, validation humaine et séparation des corpus."""

import hashlib
import json

import pytest

from sou9na_rag.regulatory import prepare_regulatory
from sou9na_rag.store import BackendError


def setup_manifest(tmp_path):
    text = "Texte fictif pour tester le parseur, sans valeur réglementaire."
    (tmp_path / "fixture.txt").write_text(text, encoding="utf-8")
    entry = {
        "source_id": "fixture",
        "file": "fixture.txt",
        "source": "Fixture technique",
        "source_url": "https://example.invalid/fixture",
        "rights": "fixture de test",
        "reviewed_by": "test-only",
        "validation": "approved",
        "sha256": hashlib.sha256(text.encode()).hexdigest(),
    }
    manifest = tmp_path / "sources.json"
    return manifest, entry


def write(manifest, entry):
    manifest.write_text(json.dumps({"documents": [entry]}), encoding="utf-8")


def test_approved_exact_file_produces_locators_not_invented_articles(tmp_path):
    manifest, entry = setup_manifest(tmp_path)
    write(manifest, entry)
    ready, chunks = prepare_regulatory(manifest)[0]
    assert ready["chunk_count"] == 1
    assert chunks[0]["article"] == "fragment 1"
    assert chunks[0]["page"] is None
    assert chunks[0]["type"] == "reglementation"


@pytest.mark.parametrize(
    "field,value,error",
    [
        ("validation", "pending", "REGULATORY_SOURCE_NOT_APPROVED"),
        ("sha256", "b" * 64, "REGULATORY_CHECKSUM_MISMATCH"),
        ("file", "../outside.txt", "INVALID_REGULATORY_PATH"),
        ("source_id", "../escape", "INVALID_REGULATORY_SOURCE_ID"),
    ],
)
def test_unapproved_changed_or_external_source_rejected(tmp_path, field, value, error):
    manifest, entry = setup_manifest(tmp_path)
    entry[field] = value
    write(manifest, entry)
    with pytest.raises(BackendError, match=error):
        prepare_regulatory(manifest)
