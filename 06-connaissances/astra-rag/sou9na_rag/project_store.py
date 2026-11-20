"""Collection Astra unique, filtres de corpus stricts et contrôle des publications."""

from .cps import CPS_APP, CPS_VERSION
from .store import AstraStore, BackendError, retry_transient


class ProjectStore(AstraStore):
    def put_cps(self, document):
        """Upsert des IDs contractuels, uniquement dans notre périmètre CPS.

        Un nouveau texte extrait du même PDF remplace ses passages en place.
        Les filtres d'instantané et la publication différée empêchent un mélange.
        """
        try:
            existing = self._find_id(document["_id"])
            if existing is None:
                return self.put_immutable(document)
            try:
                self._assert_same(existing, document)
                return False
            except BackendError:
                pass
            for key in ("rag_app", "kind", "document_id", "reference", "pipeline_version"):
                if existing.get(key) != document.get(key):
                    raise BackendError("CPS_OWNERSHIP_CONFLICT")
            if document.get("rag_app") != CPS_APP:
                raise BackendError("CPS_OWNERSHIP_CONFLICT")
            payload = dict(document)
            if payload["kind"] == "chunk":
                payload["$vectorize"] = payload["text"]
            retry_transient(
                lambda: self.collection.replace_one(
                    {
                        "_id": document["_id"],
                        "rag_app": CPS_APP,
                        "snapshot_sha256": existing.get("snapshot_sha256"),
                    },
                    payload,
                    timeout_ms=30000,
                )
            )
            saved = self._find_id(document["_id"])
            if saved is None:
                raise BackendError("CPS_WRITE_NOT_VISIBLE")
            self._assert_same(saved, document)
            return True
        except BackendError:
            raise
        except Exception:
            # Un timeout peut survenir après l'écriture : le rejeu la vérifie.
            raise BackendError("CPS_WRITE_FAILED") from None

    def verify_cps(self, manifest, chunks):
        saved = self.cps_manifest(manifest["document_id"])
        if saved is None:
            raise BackendError("CPS_MANIFEST_NOT_VISIBLE")
        self._assert_same(saved, manifest)
        self.verify_chunks(chunks)

    def verify_chunks(self, chunks):
        for chunk in chunks:
            try:
                saved = retry_transient(
                    lambda: self.collection.find_one(
                        {"_id": chunk["_id"]},
                        projection={"*": True, "$vector": True},
                        timeout_ms=30000,
                    )
                )
            except Exception:
                raise BackendError("ASTRA_VERIFICATION_FAILED") from None
            if saved is None:
                raise BackendError("CPS_CHUNK_NOT_VISIBLE")
            self._assert_same(saved, chunk)
            # Une insertion réussie ne suffit pas : vérifier le vecteur présent.
            vector = saved.get("$vector")
            if not isinstance(vector, list) or len(vector) != 1024:
                raise BackendError("CPS_VECTOR_NOT_READY")

    def cps_manifest(self, document_id):
        try:
            return self._find_id(f"cps:{document_id}:manifest")
        except Exception:
            raise BackendError("ASTRA_MANIFEST_READ_FAILED") from None

    def search_cps(self, query, manifest, count):
        filters = {
            "rag_app": CPS_APP,
            "pipeline_version": CPS_VERSION,
            "kind": "chunk",
            "type": "cps",
            "reference": manifest["reference"],
            "document_id": manifest["document_id"],
            "document_sha256": manifest["document_sha256"],
            "snapshot_sha256": manifest["snapshot_sha256"],
        }
        try:
            return retry_transient(
                lambda: list(
                    self.collection.find(
                        filters,
                        sort={"$vectorize": query},
                        limit=count,
                        include_similarity=True,
                    )
                )
            )
        except Exception:
            raise BackendError("ASTRA_SEARCH_FAILED") from None

    def regulatory_manifests(self):
        from .regulatory import REG_APP, REG_VERSION

        try:
            return list(
                self.collection.find(
                    {
                        "rag_app": REG_APP,
                        "pipeline_version": REG_VERSION,
                        "kind": "manifest",
                        "type": "reglementation",
                        "status": "ready",
                    },
                    limit=101,
                )
            )
        except Exception:
            raise BackendError("ASTRA_MANIFEST_READ_FAILED") from None

    def search_regulatory(self, query, manifest, count):
        from .regulatory import REG_APP, REG_VERSION

        try:
            return list(
                self.collection.find(
                    {
                        "rag_app": REG_APP,
                        "pipeline_version": REG_VERSION,
                        "kind": "chunk",
                        "type": "reglementation",
                        "document_sha256": manifest["document_sha256"],
                        "source_id": manifest["source_id"],
                    },
                    sort={"$vectorize": query},
                    limit=count,
                    include_similarity=True,
                )
            )
        except Exception:
            raise BackendError("ASTRA_SEARCH_FAILED") from None
