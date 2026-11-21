"""Tests des graphes sans réseau, sans jeton et sans serveur Astra."""

from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest

from sou9na_rag import graphs
from sou9na_rag.documents import CORPUS, VERSION
from sou9na_rag.store import AstraStore, BackendError, Settings


class FakeCollection:
    """Collection en mémoire qui permet de simuler pannes et courses d'insertion."""

    def __init__(self):
        self.documents = {}
        self.fail_write = False

    def find_one(self, filters, **kwargs):
        return deepcopy(self.documents.get(filters["_id"]))

    def insert_one(self, document, **kwargs):
        if self.fail_write:
            raise RuntimeError("secret-do-not-print")
        self.documents[document["_id"]] = deepcopy(document)

    def find(self, filters, **kwargs):
        docs = [
            deepcopy(d)
            for d in self.documents.values()
            if all(d.get(key) == value for key, value in filters.items())
        ]
        return docs[: kwargs.get("limit", len(docs))]


@pytest.fixture
def store():
    """Instancie uniquement l'adaptateur, sans initialiser son client réseau."""
    instance = AstraStore.__new__(AstraStore)
    instance.collection = FakeCollection()
    instance.inspect = lambda: {"provider": "fake"}
    return instance


@pytest.mark.parametrize("query", ["", " ", "a", "a" * 1001, 12, None])
def test_invalid_query_stops_before_backend(query):
    """Une requête invalide s'arrête même si l'entrée originale reste dans l'état."""
    result = graphs.build_retrieve_graph(None).invoke({"query": query})
    assert result["status"] == "invalid"
    assert result["passages"] == []


def test_wrong_corpus_stops_before_backend():
    """L'appelant ne peut pas élargir la recherche vers un autre corpus."""
    result = graphs.build_retrieve_graph(None).invoke({"query": "bonjour", "corpus": "private"})
    assert result["error"] == "INVALID_CORPUS_OR_VERSION"


def test_idempotent_writes_and_collision_rejection(store):
    """Un retry ne duplique pas le passage et ne remplace jamais un autre texte."""
    doc = {"_id": "test", "kind": "chunk", "text": "hello", "rag_app": "test"}
    assert store.put_immutable(doc) is True
    assert store.put_immutable(doc) is False
    assert len(store.collection.documents) == 1
    with pytest.raises(BackendError, match="DOCUMENT_ID_CONFLICT"):
        store.put_immutable({**doc, "text": "changed"})


def test_backend_error_is_not_no_results_or_secret_leak(store):
    """Une indisponibilité ne ressemble pas à une recherche vide."""
    store.collection.fail_write = True
    with pytest.raises(BackendError, match="ASTRA_WRITE_FAILED") as error:
        store.put_immutable({"_id": "new", "kind": "chunk", "text": "hello"})
    assert "secret" not in str(error.value)
    result = graphs.build_retrieve_graph(store).invoke({"query": "bonjour"})
    assert result["status"] == "unavailable"
    assert result["error"] == "NO_READY_DOCUMENT"


def test_partial_ingestion_never_publishes_manifest(store, monkeypatch):
    """Des passages partiels restent invisibles tant que le manifeste n'existe pas."""
    monkeypatch.setattr(graphs, "extract_pdf", lambda path: {"document_sha256": "a" * 64})
    docs = [
        {"_id": "first", "kind": "chunk", "text": "one"},
        {"_id": "second", "kind": "chunk", "text": "two"},
    ]
    monkeypatch.setattr(graphs, "make_chunks", lambda *args: docs)
    actual = store.put_immutable

    def fail_second(doc):
        if doc["_id"] == "second":
            raise BackendError("ASTRA_WRITE_FAILED")
        return actual(doc)

    store.put_immutable = fail_second
    result = graphs.build_ingest_graph(store).invoke({"path": "fake.pdf"})
    assert result["status"] == "failed"
    assert result["inserted"] == 1
    assert all(d["kind"] != "manifest" for d in store.collection.documents.values())
    with pytest.raises(BackendError, match="NO_READY_DOCUMENT"):
        store.resolve_manifest()


def test_multiple_versions_require_explicit_selection(store):
    """La recherche ne mélange pas deux éditions du PDF."""
    for digest in ("a" * 64, "b" * 64):
        store.publish({"document_sha256": digest, "document": "test.pdf", "page_count": 1}, 1)
    with pytest.raises(BackendError, match="DOCUMENT_VERSION_REQUIRED"):
        store.resolve_manifest()
    assert store.resolve_manifest("b" * 64)["document_sha256"] == "b" * 64


def test_search_is_scoped_and_returns_citations(store):
    """Les documents étrangers de la même collection ne sont pas retournés."""
    digest = "a" * 64
    store.publish({"document_sha256": digest, "document": "test.pdf", "page_count": 2}, 1)
    doc = {
        "_id": "own",
        "kind": "chunk",
        "rag_app": "sou9na_reference_rag",
        "pipeline_version": VERSION,
        "corpus": CORPUS,
        "document_sha256": digest,
        "text": "Caution test",
        "document": "test.pdf",
        "block_id": "Q-001",
        "page_start": 1,
        "page_end": 2,
        "declared_source": "Regle fictive",
        "legal_validation": "not_verified",
    }
    store.put_immutable(doc)
    store.put_immutable({**doc, "_id": "foreign", "rag_app": "other"})
    result = graphs.build_retrieve_graph(store).invoke({"query": "caution"})
    assert result["status"] == "retrieved"
    assert result["occurrences"] == 1
    assert result["passages"][0]["pages"] == [1, 2]
    assert result["passages"][0]["validation_juridique"] == "not_verified"


def test_token_hidden_and_missing_environment_rejected(monkeypatch):
    """La configuration n'affiche pas le jeton et interdit une destination arbitraire."""
    assert "SECRET" not in repr(Settings("https://db.astra.datastax.com", "SECRET"))
    monkeypatch.setenv("ASTRA_DB_API_ENDPOINT", "https://attacker.example")
    monkeypatch.setenv("ASTRA_DB_API_TOKEN", "SECRET")
    with pytest.raises(ValueError):
        Settings.from_env()


def test_retry_handles_uncertain_write_without_duplicate(store, monkeypatch):
    """Une écriture déjà appliquée avant une réponse perdue reste unique."""
    monkeypatch.setattr("sou9na_rag.store.time.sleep", lambda seconds: None)
    original = store.collection.insert_one

    def uncertain_insert(document, **kwargs):
        original(document)
        raise httpx.ReadTimeout("private upstream detail")

    store.collection.insert_one = uncertain_insert
    assert store.put_immutable({"_id": "uncertain", "kind": "chunk", "text": "sample"}) is False
    assert len(store.collection.documents) == 1


def test_embedding_model_change_is_rejected(store):
    """Le budget de tokens ne doit pas être réutilisé avec un autre modèle."""
    store.collection.options = lambda **kwargs: SimpleNamespace(
        vector=SimpleNamespace(
            dimension=1536, service=SimpleNamespace(provider="other", model_name="other")
        )
    )
    with pytest.raises(BackendError, match="UNSUPPORTED_EMBEDDING_MODEL"):
        AstraStore.inspect(store)


def test_republished_manifest_keeps_original_timestamp(store):
    """Le rapport de reprise reflète le manifeste persisté, pas une nouvelle création."""
    source = {"document_sha256": "a" * 64, "document": "test.pdf", "page_count": 1}
    first = store.publish(source, 1)
    second = store.publish(source, 1)
    assert first == second
    assert len(store.collection.documents) == 1
