"""Point d'intégration pour Agentic AI ou la future enveloppe MCP de Mhalli."""

from typing import Any

from .documents import CORPUS
from .graphs import build_retrieve_graph
from .store import AstraStore, Settings


def chercher(
    requete: str,
    corpus: str = CORPUS,
    *,
    top_k: int = 5,
    document_sha256: str | None = None,
    store: Any = None,
) -> dict:
    """Retourne les passages cités et un état explicite, jamais une réponse inventée."""
    backend = store if store is not None else AstraStore(Settings.from_env())
    state = build_retrieve_graph(backend).invoke(
        {
            "query": requete,
            "corpus": corpus,
            "top_k": top_k,
            **({"document_sha256": document_sha256} if document_sha256 is not None else {}),
        }
    )
    return {
        key: state[key] for key in ("status", "error", "occurrences", "passages") if key in state
    }
