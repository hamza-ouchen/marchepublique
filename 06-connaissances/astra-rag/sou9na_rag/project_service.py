"""Contrat MCP J5 pour FAQ de référence, réglementation validée et CPS."""

import math

from .cps import CPS_APP, CPS_VERSION, fingerprint
from .documents import CORPUS
from .service import chercher as chercher_reference
from .store import BackendError
from .token_budget import MAX_TOKENS, token_count


def _result(passages=None, error=None):
    passages = passages or []
    needs_review = not passages or any(
        p.get("validation_juridique") != "approved_by_team" for p in passages
    )
    return {
        "passages": passages,
        "vide": not passages,
        "citation_imposee": True,
        "hitl": needs_review,
        **({"erreur": error} if error else {}),
    }


def chercher_projet(
    requete, corpus="faq", nombre=5, *, store=None, repository=None, min_score=0.75
):
    """Recherche seulement dans le corpus demandé ; aucun repli non filtré."""
    if (
        not isinstance(requete, str)
        or not 2 <= len(requete.strip()) <= 1000
        or token_count(requete) > MAX_TOKENS
    ):
        return _result(error="requete_invalide")
    if type(nombre) is not int or not 1 <= nombre <= 5:
        return _result(error="nombre_invalide")
    if not isinstance(corpus, str) or not (
        corpus in ("faq", "reglementation", CORPUS)
        or (corpus.startswith("cps:") and 1 <= len(corpus[4:]) <= 200)
    ):
        return _result(error="corpus_invalide")
    if not isinstance(min_score, (int, float)) or not 0 <= min_score <= 1:
        return _result(error="seuil_invalide")
    try:
        if store is None:
            from .project_store import ProjectStore
            from .store import Settings

            store = ProjectStore(Settings.from_env())
        store.inspect()
        if corpus in ("faq", CORPUS):
            reference = chercher_reference(requete, store=store, top_k=nombre)
            if reference.get("error"):
                return _result(error=reference["error"])
            documents = [
                {
                    **p,
                    "text": p["texte"],
                    "article": p["bloc"],
                    "page": p["pages"],
                    "$similarity": p["score"],
                    "legal_validation": p["validation_juridique"],
                }
                for p in reference["passages"]
            ]
        elif corpus == "reglementation":
            manifests = store.regulatory_manifests()
            if not manifests:
                return _result(error="CORPUS_REGLEMENTAIRE_NON_PUBLIE")
            if len(manifests) > 100:
                return _result(error="TOO_MANY_REGULATORY_DOCUMENTS")
            # Plusieurs versions d'une même source exigent une décision explicite.
            if len({m["source_id"] for m in manifests}) != len(manifests):
                return _result(error="REGULATORY_VERSION_REQUIRED")
            documents = [d for m in manifests for d in store.search_regulatory(requete, m, nombre)]
        else:
            if repository is None:
                from .postgres import CpsRepository

                repository = CpsRepository()
            documents = []
            for doc, sections in repository.ready_snapshots(corpus[4:]):
                manifest = store.cps_manifest(doc["id"])
                if not manifest or any(
                    (
                        manifest.get("status") != "ready",
                        manifest.get("rag_app") != CPS_APP,
                        manifest.get("pipeline_version") != CPS_VERSION,
                        manifest.get("reference") != corpus[4:],
                        manifest.get("document_id") != doc["id"],
                        manifest.get("document_sha256") != doc["sha256"],
                        manifest.get("snapshot_sha256") != fingerprint(doc, sections),
                    )
                ):
                    return _result(error="CPS_PUBLICATION_INCOHERENTE")
                documents.extend(store.search_cps(requete, manifest, nombre))
        passages = []
        for doc in documents:
            score = doc.get("$similarity")
            if (
                not isinstance(score, (int, float))
                or not math.isfinite(score)
                or not min_score <= score <= 1
            ):
                continue
            if not all(
                isinstance(doc.get(k), str) and doc[k].strip()
                for k in ("text", "source", "article")
            ):
                continue
            passages.append(
                {
                    "texte": doc["text"],
                    "source": doc["source"],
                    "article": doc["article"],
                    "score": score,
                    "page": doc.get("page"),
                    "source_id": doc.get("source_id") or doc.get("_id"),
                    "document_id": doc.get("document_id"),
                    "reference": doc.get("reference"),
                    "validation_juridique": doc.get("legal_validation", "not_verified"),
                }
            )
        passages.sort(key=lambda p: p["score"], reverse=True)
        return _result(passages[:nombre])
    except (BackendError, ValueError):
        return _result(error="rag_indisponible")
    except Exception:
        # Ne propage pas d'URL, token ou texte d'exception du fournisseur au flow.
        return _result(error="rag_indisponible")
