"""Parcours CPS → Astra → recherche, avec pannes et rejeux, sans services réels."""

import json
import re
from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path

import pytest

from sou9na_rag.cps import cps_chunks, ingest_cps
from sou9na_rag.project_service import chercher_projet
from sou9na_rag.project_store import ProjectStore
from sou9na_rag.store import BackendError
from sou9na_rag.token_budget import MAX_TOKENS, token_count

FIXTURES = Path(__file__).resolve().parents[3] / "02-backend/fixtures/cps/attendu"


class Collection:
    def __init__(self):
        self.documents = {}
        self.fail_at = None
        self.vectors_ready = True
        self.filters = []

    def find_one(self, filters, **kwargs):
        return deepcopy(self.documents.get(filters["_id"]))

    def insert_one(self, document, **kwargs):
        if self.fail_at == document["_id"]:
            raise RuntimeError("secret-must-not-escape")
        saved = deepcopy(document)
        if saved["kind"] == "chunk" and self.vectors_ready:
            saved["$vector"] = [0.1] * 1024
        self.documents[saved["_id"]] = saved

    def find(self, filters, **kwargs):
        self.filters.append(filters)
        docs = [
            deepcopy(d)
            for d in self.documents.values()
            if all(d.get(k) == v for k, v in filters.items())
        ]
        for doc in docs:
            # Simule les scores du fournisseur, sans prétendre mesurer les embeddings.
            doc["$similarity"] = 0.9 if "caution" in doc.get("text", "").lower() else 0.8
        docs.sort(key=lambda d: d["$similarity"], reverse=True)
        return docs[: kwargs.get("limit", len(docs))]

    def replace_one(self, filters, replacement, **kwargs):
        old = self.documents.get(filters["_id"])
        if old and all(old.get(k) == v for k, v in filters.items()):
            self.insert_one(replacement)


class Repository:
    def __init__(self, fixture="a1-0123-cps.json", document_id=1):
        data = json.loads((FIXTURES / fixture).read_text(encoding="utf-8"))
        self.document = {
            "id": document_id,
            "reference": data["reference"],
            "filename": data["document_name"],
            "sha256": "a" * 64,
            "doc_type": "CPS",
            "statut": "extracted",
        }
        self.sections = data["sections"]
        if self.sections:
            text = (FIXTURES.parent / data["source_verite_terrain"]).read_text(encoding="utf-8")
            headings = list(re.finditer(r"(?m)^(\d+(?:\.\d+)*)(?:\.)?\s+([A-ZÉÈÀ].*)$", text))
            bodies = {}
            for i, match in enumerate(headings):
                end = headings[i + 1].start() if i + 1 < len(headings) else len(text)
                bodies[match[1]] = text[match.end() : end].strip()
            for section in self.sections:
                section["texte"] = bodies[section["numero"]]
                assert section["texte"].startswith(section["debut"])
                assert len(section["texte"]) == section["longueur"]
        self.logs = []

    @contextmanager
    def session(self, document_id):
        assert document_id == self.document["id"]
        yield self

    def snapshot(self):
        return deepcopy(self.document), deepcopy(self.sections)

    def finish(self, status, reason, run_id, tokens):
        self.document["statut"] = status
        self.document["echec_raison"] = reason
        self.logs.append((run_id, status, tokens))

    def ready_snapshots(self, reference):
        if self.document["statut"] == "ready" and self.document["reference"] == reference:
            return [self.snapshot()]
        return []


@pytest.fixture
def store():
    result = ProjectStore.__new__(ProjectStore)
    result.collection = Collection()
    result.inspect = lambda: {"dimension": 1024}
    return result


def test_a1_ingestion_retrieval_and_idempotence(store):
    repo = Repository()
    first = ingest_cps(repo, store, 1)
    assert first["status"] == "ready"
    assert first["upserted"] == 7
    count = len(store.collection.documents)
    again = ingest_cps(repo, store, 1)
    assert again["upserted"] == 0 and again["skipped"] == 7
    assert len(store.collection.documents) == count
    result = chercher_projet(
        "caution provisoire", "cps:2026/DTR/0123", 3, store=store, repository=repo
    )
    assert len(result["passages"]) == 3 and result["citation_imposee"]
    assert all(
        p["source"] and p["article"] and p["reference"] == "2026/DTR/0123"
        for p in result["passages"]
    )
    assert "caution" in result["passages"][0]["texte"].lower()
    assert len(repo.logs) == 2


def test_partial_ingestion_invisible_and_retry_skips_existing(store):
    repo = Repository()
    store.collection.fail_at = "cps:1:3:0"
    result = ingest_cps(repo, store, 1)
    assert result["status"] == "failed" and result["upserted"] > 0
    assert repo.document["statut"] == "echec"
    assert store.cps_manifest(1) is None
    assert (
        chercher_projet("caution", "cps:2026/DTR/0123", store=store, repository=repo)["passages"]
        == []
    )
    # La reprise après echec exige le retour à extracted par le producteur.
    repo.document["statut"] = "extracted"
    store.collection.fail_at = None
    retry = ingest_cps(repo, store, 1)
    assert retry["status"] == "ready" and retry["skipped"] > 0


def test_missing_vectors_cannot_mark_ready(store):
    repo = Repository()
    store.collection.vectors_ready = False
    result = ingest_cps(repo, store, 1)
    assert result["error"] == "CPS_VECTOR_NOT_READY"
    assert repo.document["statut"] == "echec"


def test_corrected_sections_are_reindexed_in_place_after_publication(store):
    repo = Repository()
    ingest_cps(repo, store, 1)
    repo.sections[0]["texte"] += " Modification ultérieure."
    result = chercher_projet("caution", "cps:2026/DTR/0123", store=store, repository=repo)
    assert result["erreur"] == "CPS_PUBLICATION_INCOHERENTE"
    before = len(store.collection.documents)
    assert ingest_cps(repo, store, 1)["status"] == "ready"
    assert len(store.collection.documents) == before
    assert not chercher_projet("caution", "cps:2026/DTR/0123", store=store, repository=repo).get(
        "erreur"
    )


def test_upsert_cannot_replace_another_owners_document(store):
    repo = Repository()
    ingest_cps(repo, store, 1)
    store.collection.documents["cps:1:1:0"]["rag_app"] = "another-application"
    assert ingest_cps(repo, store, 1)["error"] == "CPS_OWNERSHIP_CONFLICT"


def test_a2_addenda_keeps_distinct_citable_documents(store):
    principal = Repository("a2-0124-cps.json", 2)
    addenda = Repository("a2-0124-addenda-1.json", 3)
    assert ingest_cps(principal, store, 2)["status"] == "ready"
    assert ingest_cps(addenda, store, 3)["status"] == "ready"
    chunks = [d for d in store.collection.documents.values() if d["kind"] == "chunk"]
    assert {d["document_id"] for d in chunks} == {2, 3}
    assert {d["filename"] for d in chunks} == {"cps.pdf", "addenda-1.pdf"}


def test_a3_no_sections_is_explicit_failure(store):
    repo = Repository("a3-0131-cps.json")
    assert ingest_cps(repo, store, 1)["error"] == "CPS_SECTIONS_REQUIRED"
    assert not store.collection.documents


def test_ready_in_astra_alone_does_not_publish_cps(store):
    repo = Repository()
    ingest_cps(repo, store, 1)
    repo.document["statut"] = "extracted"
    assert (
        chercher_projet("caution", "cps:2026/DTR/0123", store=store, repository=repo)["passages"]
        == []
    )


def test_reference_isolation_and_no_unfiltered_fallback(store):
    repo = Repository()
    ingest_cps(repo, store, 1)
    assert chercher_projet("caution", "cps:OTHER", store=store, repository=repo)["passages"] == []
    chercher_projet("caution", "cps:2026/DTR/0123", store=store, repository=repo)
    assert all(
        f.get("reference") == "2026/DTR/0123" and f.get("snapshot_sha256")
        for f in store.collection.filters
    )


def test_low_score_and_invalid_citation_abstain(store):
    repo = Repository()
    ingest_cps(repo, store, 1)
    result = chercher_projet(
        "autre sujet", "cps:2026/DTR/0123", store=store, repository=repo, min_score=0.99
    )
    assert result["passages"] == [] and result["hitl"]
    for doc in store.collection.documents.values():
        if doc["kind"] == "chunk":
            doc["article"] = ""
    assert (
        chercher_projet("caution", "cps:2026/DTR/0123", store=store, repository=repo)["passages"]
        == []
    )


@pytest.mark.parametrize(
    "kwargs",
    [
        {"requete": ""},
        {"requete": None},
        {"requete": "a" * 1001},
        {"requete": "question", "corpus": "cps:"},
        {"requete": "question", "corpus": "private"},
        {"requete": "question", "nombre": 6},
        {"requete": "question", "nombre": True},
    ],
)
def test_invalid_request_never_constructs_backend(kwargs):
    assert chercher_projet(**kwargs)["erreur"]


def test_long_arabic_section_preserves_budget():
    repo = Repository()
    repo.sections[0]["texte"] = "مرحبا شروط الصفقة العمومية " * 500
    chunks = cps_chunks(*repo.snapshot())
    assert all(token_count(c["text"]) <= MAX_TOKENS for c in chunks)
    assert sum(c["section_no"] == 1 for c in chunks) > 1


def test_no_regulatory_fallback_to_faq(store):
    result = chercher_projet("caution", "reglementation", store=store)
    assert result["erreur"] == "CORPUS_REGLEMENTAIRE_NON_PUBLIE"


def test_external_errors_do_not_expose_secrets(store):
    store.inspect = lambda: (_ for _ in ()).throw(RuntimeError("top-secret-token"))
    result = chercher_projet("caution", "faq", store=store)
    assert result["erreur"] == "rag_indisponible"
    assert "secret" not in json.dumps(result)


def test_invalid_section_order_is_not_ingested():
    repo = Repository()
    repo.sections.reverse()
    with pytest.raises(BackendError, match="INVALID_SECTION_ORDER"):
        cps_chunks(*repo.snapshot())
