"""Adaptateur Astra : documents immuables et publication après ingestion complète."""

import os
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

import httpx
from astrapy import DataAPIClient

from .documents import APP, CORPUS, VERSION


def retry_transient(operation):
    """Rejoue au plus trois fois les erreurs réseau/serveur, jamais une donnée refusée."""
    for attempt in range(3):
        try:
            return operation()
        except Exception as exc:
            codes = [
                getattr(item, "error_code", "") for item in getattr(exc, "error_descriptors", [])
            ]
            transient = isinstance(exc, httpx.TransportError) or "Timeout" in type(exc).__name__
            transient = transient or any(
                any(
                    marker in code
                    for marker in ("RATE_LIMIT", "TIMEOUT", "SERVER_ERROR", "UNAVAILABLE")
                )
                for code in codes
            )
            if not transient or attempt == 2:
                raise
            time.sleep(0.5 * (2**attempt))


class BackendError(RuntimeError):
    """Erreur contrôlée, sans reprise de messages susceptibles de contenir un secret."""


@dataclass(frozen=True)
class Settings:
    """Configuration chargée exclusivement depuis l'environnement du processus."""

    endpoint: str
    token: str = field(repr=False)
    collection: str = "sou9na"
    keyspace: str = "default_keyspace"

    @classmethod
    def from_env(cls) -> "Settings":
        """Vérifie la destination sans afficher le jeton."""
        endpoint = os.environ.get("ASTRA_DB_API_ENDPOINT", "").rstrip("/")
        token = os.environ.get("ASTRA_DB_API_TOKEN", "")
        url = urlparse(endpoint)
        if (
            url.scheme != "https"
            or not (url.hostname or "").endswith(".astra.datastax.com")
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path
        ):
            raise ValueError("ASTRA_DB_API_ENDPOINT doit etre une URL HTTPS Astra valide")
        if not token:
            raise ValueError("ASTRA_DB_API_TOKEN est requis")
        return cls(
            endpoint,
            token,
            os.environ.get("ASTRA_DB_COLLECTION", "sou9na"),
            os.environ.get("ASTRA_DB_KEYSPACE", "default_keyspace"),
        )


class AstraStore:
    """N'accède qu'à la collection choisie et au périmètre documentaire de ce module."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.database = DataAPIClient().get_database(
            settings.endpoint, token=settings.token, keyspace=settings.keyspace
        )
        self.collection = self.database.get_collection(settings.collection)

    def inspect(self) -> dict[str, Any]:
        """Vérifie que vectorize existe ; ne crée ni ne reconfigure de collection."""
        try:
            options = retry_transient(lambda: self.collection.options(timeout_ms=30000))
            vector = options.vector
            if not vector or not vector.service:
                raise BackendError("VECTORIZE_REQUIRED")
            if (
                vector.service.provider != "nvidia"
                or vector.service.model_name != "nvidia/nv-embedqa-e5-v5"
                or vector.dimension != 1024
            ):
                raise BackendError("UNSUPPORTED_EMBEDDING_MODEL")
            return {
                "collection": self.settings.collection,
                "dimension": vector.dimension,
                "provider": vector.service.provider,
                "model": vector.service.model_name,
            }
        except BackendError:
            raise
        except Exception:
            raise BackendError("ASTRA_INSPECTION_FAILED") from None

    def _find_id(self, document_id: str) -> dict | None:
        return retry_transient(
            lambda: self.collection.find_one({"_id": document_id}, timeout_ms=30000)
        )

    def put_immutable(self, document: dict) -> bool:
        """Insère sans écraser ; accepte une réexécution strictement identique."""
        payload = dict(document)
        if payload["kind"] == "chunk":
            payload["$vectorize"] = payload["text"]
        try:
            existing = self._find_id(payload["_id"])
            if existing is not None:
                self._assert_same(existing, document)
                return False
            try:
                retry_transient(lambda: self.collection.insert_one(payload, timeout_ms=30000))
                return True
            except Exception:
                # Une insertion peut avoir abouti avant un timeout ou une course.
                existing = self._find_id(payload["_id"])
                if existing is None:
                    raise BackendError("ASTRA_WRITE_FAILED") from None
                self._assert_same(existing, document)
                return False
        except BackendError:
            raise
        except Exception:
            raise BackendError("ASTRA_WRITE_FAILED") from None

    @staticmethod
    def _assert_same(existing: dict, expected: dict) -> None:
        """Refuse une collision d'identifiant ou une reprise d'un autre corpus."""
        volatile = {"created_at"}
        for key, value in expected.items():
            if key not in volatile and existing.get(key) != value:
                raise BackendError("DOCUMENT_ID_CONFLICT")

    def publish(self, extracted: dict, chunk_count: int) -> dict:
        """Publie un manifeste seulement après succès de tous les passages."""
        manifest = {
            "_id": f"s9rag:{VERSION}:{extracted['document_sha256']}:manifest",
            "rag_app": APP,
            "kind": "manifest",
            "corpus": CORPUS,
            "pipeline_version": VERSION,
            "document_sha256": extracted["document_sha256"],
            "document": extracted["document"],
            "page_count": extracted["page_count"],
            "chunk_count": chunk_count,
            "status": "ready",
            "created_at": datetime.now(UTC).isoformat(),
        }
        inserted = self.put_immutable(manifest)
        if not inserted:
            existing = self._find_id(manifest["_id"])
            if existing is None:
                raise BackendError("ASTRA_MANIFEST_READ_FAILED")
            return {key: existing[key] for key in manifest}
        return manifest

    def resolve_manifest(self, document_sha256: str | None = None) -> dict:
        """Exige une version explicite si plusieurs PDF sont publiés."""
        filters = {
            "rag_app": APP,
            "kind": "manifest",
            "corpus": CORPUS,
            "pipeline_version": VERSION,
            "status": "ready",
        }
        if document_sha256:
            filters["document_sha256"] = document_sha256
        try:
            manifests = list(self.collection.find(filters, limit=2))
        except Exception:
            raise BackendError("ASTRA_MANIFEST_READ_FAILED") from None
        if not manifests:
            raise BackendError("NO_READY_DOCUMENT")
        if len(manifests) != 1:
            raise BackendError("DOCUMENT_VERSION_REQUIRED")
        return manifests[0]

    def search(self, query: str, manifest: dict, top_k: int) -> list[dict]:
        """Recherche vectorielle limitée à une version complète de ce corpus public."""
        filters = {
            "rag_app": APP,
            "kind": "chunk",
            "corpus": CORPUS,
            "pipeline_version": VERSION,
            "document_sha256": manifest["document_sha256"],
        }
        try:
            return list(
                self.collection.find(
                    filters, sort={"$vectorize": query}, limit=top_k, include_similarity=True
                )
            )
        except Exception:
            raise BackendError("ASTRA_SEARCH_FAILED") from None
