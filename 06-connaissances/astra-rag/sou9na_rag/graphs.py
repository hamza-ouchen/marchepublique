"""Deux graphes indépendants, avec erreurs explicites et sources vérifiables."""

import re
from typing import Any, TypedDict

from langgraph.graph import END, StateGraph

from .documents import CORPUS, DocumentError, extract_pdf, make_chunks
from .store import BackendError
from .token_budget import MAX_TOKENS, token_count


class IngestState(TypedDict, total=False):
    """État d'ingestion d'un PDF public fourni par l'équipe."""

    path: str
    expected_questions: int
    extracted: dict
    chunks: list[dict]
    inserted: int
    skipped: int
    status: str
    error: str
    manifest: dict


class RetrieveState(TypedDict, total=False):
    """État de recherche, distinct d'une réponse générée ou d'un verdict juridique."""

    query: str
    corpus: str
    document_sha256: str
    top_k: int
    status: str
    error: str
    passages: list[dict]
    occurrences: int
    manifest: dict


def build_ingest_graph(store: Any):
    """Extrait, découpe, stocke puis publie ; une erreur arrête la chaîne."""

    def parse(state: IngestState) -> dict:
        try:
            extracted = extract_pdf(state["path"])
            return {"extracted": extracted, "status": "parsed", "error": ""}
        except (DocumentError, OSError, ValueError):
            return {"status": "failed", "error": "PDF_INVALID_OR_UNREADABLE"}

    def chunk(state: IngestState) -> dict:
        try:
            chunks = make_chunks(state["extracted"], state.get("expected_questions", 125))
            return {"chunks": chunks, "status": "chunked"}
        except (DocumentError, ValueError):
            return {"status": "failed", "error": "PDF_STRUCTURE_INVALID"}

    def save(state: IngestState) -> dict:
        inserted = skipped = 0
        try:
            store.inspect()
            for document in state["chunks"]:
                if store.put_immutable(document):
                    inserted += 1
                else:
                    skipped += 1
            manifest = store.publish(state["extracted"], len(state["chunks"]))
            return {
                "inserted": inserted,
                "skipped": skipped,
                "manifest": manifest,
                "status": "ready",
            }
        except BackendError as exc:
            return {"inserted": inserted, "skipped": skipped, "status": "failed", "error": str(exc)}

    graph = StateGraph(IngestState)
    graph.add_node("extract_pdf", parse)
    graph.add_node("split_qa_and_pages", chunk)
    graph.add_node("store_and_publish", save)
    graph.set_entry_point("extract_pdf")
    graph.add_conditional_edges(
        "extract_pdf", lambda s: END if s.get("error") else "split_qa_and_pages"
    )
    graph.add_conditional_edges(
        "split_qa_and_pages", lambda s: END if s.get("error") else "store_and_publish"
    )
    graph.add_edge("store_and_publish", END)
    return graph.compile()


def build_retrieve_graph(store: Any):
    """Valide la requête, sélectionne une version publiée puis retourne des passages."""

    def normalize(state: RetrieveState) -> dict:
        query = state.get("query", "")
        top_k = state.get("top_k", 5)
        if not isinstance(query, str) or not 2 <= len(query.strip()) <= 1000:
            return {"status": "invalid", "error": "INVALID_QUERY", "passages": [], "occurrences": 0}
        if token_count(query) > MAX_TOKENS:
            return {
                "status": "invalid",
                "error": "QUERY_TOKEN_LIMIT",
                "passages": [],
                "occurrences": 0,
            }
        if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= 20:
            return {"status": "invalid", "error": "INVALID_TOP_K", "passages": [], "occurrences": 0}
        digest = state.get("document_sha256")
        if state.get("corpus", CORPUS) != CORPUS or (
            digest is not None
            and (not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest))
        ):
            return {
                "status": "invalid",
                "error": "INVALID_CORPUS_OR_VERSION",
                "passages": [],
                "occurrences": 0,
            }
        return {"query": query.strip(), "top_k": top_k, "status": "normalized", "error": ""}

    def search(state: RetrieveState) -> dict:
        try:
            store.inspect()
            manifest = store.resolve_manifest(state.get("document_sha256"))
            documents = store.search(state["query"], manifest, state["top_k"])
            passages = [
                {
                    "texte": doc["text"],
                    "source": doc["document"],
                    "source_id": doc["_id"],
                    "document_sha256": doc["document_sha256"],
                    "bloc": doc["block_id"],
                    "pages": [doc["page_start"], doc["page_end"]],
                    "source_declaree": doc["declared_source"],
                    "validation_juridique": doc["legal_validation"],
                    "score": doc.get("$similarity"),
                }
                for doc in documents
            ]
            return {
                "manifest": manifest,
                "passages": passages,
                "occurrences": len(passages),
                "status": "retrieved" if passages else "no_match",
            }
        except BackendError as exc:
            return {"status": "unavailable", "error": str(exc), "passages": [], "occurrences": 0}

    graph = StateGraph(RetrieveState)
    graph.add_node("validate_query", normalize)
    graph.add_node("retrieve_cited_passages", search)
    graph.set_entry_point("validate_query")
    graph.add_conditional_edges(
        "validate_query", lambda s: END if s.get("error") else "retrieve_cited_passages"
    )
    graph.add_edge("retrieve_cited_passages", END)
    return graph.compile()
