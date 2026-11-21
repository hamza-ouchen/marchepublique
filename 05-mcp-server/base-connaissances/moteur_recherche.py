# ═══════════════════════════════════════════════════════════════════
# SOU9NA — MCP base-connaissances · moteur de recherche
#
# Deux sources, un seul contrat de sortie :
#   • corpus statiques locaux (faq, reglementation) → JSON versionnés ;
#   • corpus CPS (`cps:<reference>`) → Astra DB, collection `sou9na`.
#
# Règles :
#   • JAMAIS d'exception qui remonte : une base vide, un corpus absent ou
#     Astra injoignable renvoient une réponse structurée (`vide: true`).
#   • Chaque passage porte `texte`, `source`, `article`, `score` — une
#     réponse sans citation est rejetée (contrat J5).
#   • 5 passages maximum, quelles que soient les valeurs reçues.
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import math
import os
import unicodedata
from pathlib import Path

import httpx

CORPUS_STATIQUES = ("faq", "reglementation")
CORPUS_VALIDES = CORPUS_STATIQUES          # compatibilité (anciens imports)
PREFIXE_CPS = "cps:"
NOMBRE_PAR_DEFAUT = 5
NOMBRE_MAX = 5
ASTRA_LIMITE_CANDIDATS = 500
ASTRA_TIMEOUT = 8.0

CORPUS_DIR = Path(os.environ.get("CORPUS_DIR", "corpus"))

_STOPWORDS = {
    "le", "la", "les", "de", "des", "du", "un", "une", "et", "ou", "a", "au",
    "aux", "en", "dans", "pour", "par", "sur", "avec", "sans", "est", "sont",
    "ce", "cette", "ces", "il", "elle", "ils", "elles", "que", "qui", "quoi",
    "dont", "se", "sa", "son", "ses", "leur", "leurs", "plus", "pas", "ne",
    "the", "of", "to", "and", "is", "are", "what", "how",
}


# ── Normalisation ───────────────────────────────────────────────────
def _normaliser(texte: str) -> list[str]:
    """Minuscule, sans accents, sans ponctuation → tokens (≥ 2 caractères)."""
    sans_accents = unicodedata.normalize("NFD", (texte or "").lower())
    sans_accents = "".join(c for c in sans_accents if unicodedata.category(c) != "Mn")
    tokens = []
    for mot in "".join(c if c.isalnum() else " " for c in sans_accents).split():
        if len(mot) < 2 or mot in _STOPWORDS:
            continue
        tokens.append(mot)
    return tokens


def _tokens_requete(requete: str) -> list[str]:
    return list(dict.fromkeys(_normaliser(requete)))


def _correspond(mot_document: str, mot_requete: str) -> bool:
    """Égalité ou racine commune (pluriels, féminins) — jamais sous 4 lettres."""
    if mot_document == mot_requete:
        return True
    if len(mot_document) < 4 or len(mot_requete) < 4:
        return False
    return mot_document.startswith(mot_requete) or mot_requete.startswith(mot_document)


def corpus_valide(corpus: str) -> bool:
    if not isinstance(corpus, str):
        return False
    if corpus in CORPUS_STATIQUES:
        return True
    return corpus.startswith(PREFIXE_CPS) and len(corpus) > len(PREFIXE_CPS)


def _borne(nombre: int) -> int:
    try:
        return max(1, min(int(nombre), NOMBRE_MAX))
    except (TypeError, ValueError):
        return NOMBRE_PAR_DEFAUT


# ── Corpus locaux ───────────────────────────────────────────────────
def _charger_corpus(corpus: str) -> tuple[list[dict], str | None]:
    """Retourne (passages, souci). Ne lève jamais."""
    fichier = Path(CORPUS_DIR) / f"{corpus}.json"
    if not fichier.exists():
        return [], "corpus_absent"
    try:
        donnees = json.loads(fichier.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return [], "corpus_illisible"
    passages = donnees.get("passages") if isinstance(donnees, dict) else donnees
    if not isinstance(passages, list):
        return [], "corpus_illisible"
    return [p for p in passages if isinstance(p, dict)], None


def _est_cite(passage: dict) -> bool:
    return bool(
        str(passage.get("texte", "")).strip()
        and str(passage.get("source", "")).strip()
        and str(passage.get("article", "")).strip()
    )


def _classer(requete: str, passages: list[dict], nombre: int) -> tuple[list[dict], int]:
    """Score lexical déterministe (tf·idf + couverture + bonus de phrase).

    Retourne (meilleurs passages, nombre de passages écartés faute de citation).
    """
    tokens = _tokens_requete(requete)
    if not tokens or not passages:
        return [], 0

    documents = [
        _normaliser(
            f"{p.get('texte', '')} {p.get('source', '')} "
            f"{p.get('article', '')} {p.get('titre', '')}"
        )
        for p in passages
    ]

    total = len(documents)
    idf: dict[str, float] = {}
    for token in tokens:
        df = sum(1 for doc in documents if any(_correspond(d, token) for d in doc))
        idf[token] = math.log((total + 1) / (df + 1)) + 1.0

    phrase = " ".join(tokens)
    scores: list[tuple[float, int, dict]] = []
    ignores = 0

    for index, (passage, doc) in enumerate(zip(passages, documents)):
        if not _est_cite(passage):
            ignores += 1
            continue

        score = 0.0
        couverts = 0
        for token in tokens:
            occurrences = sum(1 for d in doc if _correspond(d, token))
            if occurrences:
                couverts += 1
                score += idf[token] * (1.0 + math.log(occurrences))

        if not couverts:
            continue

        couverture = couverts / len(tokens)
        score *= 0.6 + 0.4 * couverture              # une requête bien couverte gagne
        if len(tokens) > 1 and phrase in " ".join(doc):
            score += 0.8                             # expression exacte

        scores.append((score, index, passage))

    scores.sort(key=lambda element: (-element[0], element[1]))
    resultats = [
        {
            "texte": str(passage.get("texte", "")).strip(),
            "source": str(passage.get("source", "")).strip(),
            "article": str(passage.get("article", "")).strip(),
            "score": round(score, 4),
        }
        for score, _, passage in scores[:nombre]
    ]
    return resultats, ignores


def chercher_lexical(requete: str, corpus: str, nombre: int = NOMBRE_PAR_DEFAUT) -> list[dict]:
    passages, _ = _charger_corpus(corpus)
    resultats, _ = _classer(requete, passages, _borne(nombre))
    return resultats


# ── Astra DB (CPS et repli) ─────────────────────────────────────────
def _astra_config() -> dict | None:
    endpoint = os.environ.get("ASTRA_DB_API_ENDPOINT", "").strip().rstrip("/")
    token = os.environ.get("ASTRA_DB_API_TOKEN", "").strip()
    if not endpoint or not token:
        return None
    return {
        "endpoint": endpoint,
        "token": token,
        "collection": os.environ.get("ASTRA_DB_COLLECTION", "sou9na").strip() or "sou9na",
        "keyspace": os.environ.get("ASTRA_DB_KEYSPACE", "default_keyspace").strip()
                    or "default_keyspace",
    }


def _astra_appel(config: dict, corps: dict) -> dict:
    url = (
        f"{config['endpoint']}/api/json/v1/{config['keyspace']}/{config['collection']}"
    )
    reponse = httpx.post(
        url,
        headers={"Token": config["token"], "Content-Type": "application/json"},
        json=corps,
        timeout=ASTRA_TIMEOUT,
    )
    reponse.raise_for_status()
    return reponse.json()


def _astra_compter(config: dict) -> int:
    donnees = _astra_appel(config, {"countDocuments": {}})
    return int(donnees.get("status", {}).get("count", 0))


def _astra_lire(config: dict, corpus: str, limite: int = ASTRA_LIMITE_CANDIDATS) -> list[dict]:
    filtre = {"type": "cps" if corpus.startswith(PREFIXE_CPS) else corpus}
    donnees: list[dict] = []

    for essai_filtre in (filtre, None):             # repli sans filtre si schéma différent
        requete = {"find": {"limit": limite}}
        if essai_filtre:
            requete["find"]["filter"] = essai_filtre
        reponse = _astra_appel(config, requete)
        donnees = reponse.get("data", {}).get("documents", []) or []
        if donnees or essai_filtre is None:
            break
    return donnees


def _filtrer_corpus(documents: list[dict], corpus: str) -> list[dict]:
    if not corpus.startswith(PREFIXE_CPS):
        return [
            d for d in documents
            if str(d.get("type", corpus)) in (corpus, "") or "type" not in d
        ]
    reference = corpus[len(PREFIXE_CPS):]
    return [
        d for d in documents
        if d.get("reference") == reference or d.get("corpus") == corpus
    ]


def _passage_astra(document: dict, corpus: str) -> dict:
    texte = document.get("texte") or document.get("text") or document.get("contenu") or ""
    source = (
        document.get("source") or document.get("document")
        or document.get("filename") or document.get("reference") or corpus
    )
    article = document.get("article") or document.get("numero") or document.get("titre") or ""
    if not article and document.get("section_no") is not None:
        article = f"section {document['section_no']}"
    return {
        "texte": str(texte).strip(),
        "source": str(source).strip(),
        "article": str(article).strip(),
    }


def _resultat(requete: str, corpus: str, moteur: str, passages: list[dict], *,
              message: str | None = None, erreur: str | None = None,
              astra: dict | None = None, ignores: int = 0) -> dict:
    resultat = {
        "requete": requete,
        "corpus": corpus,
        "moteur": moteur,
        "passages": passages,
        "vide": not passages,
    }
    if message:
        resultat["message"] = message
    if erreur:
        resultat["erreur"] = erreur
    if astra:
        resultat["astra"] = astra
    if ignores:
        resultat["ignores"] = ignores
    return resultat


def _chercher_astra(requete: str, corpus: str, nombre: int) -> dict | None:
    """Retourne un résultat structuré, ou None si Astra n'est pas configuré."""
    config = _astra_config()
    if not config:
        return None

    collection = config["collection"]
    try:
        total = _astra_compter(config)
    except Exception as erreur:                       # réseau, token, TLS…
        return _resultat(
            requete, corpus, "astra", [],
            erreur="astra_indisponible",
            message="La base documentaire est momentanément injoignable.",
            astra={"collection": collection, "documents": None,
                   "detail": type(erreur).__name__},
        )

    if total == 0:
        return _resultat(
            requete, corpus, "astra", [],
            message=(
                "La collection « sou9na » est vide : aucun document n'a encore "
                "été ingéré. La recherche reprendra dès la première ingestion."
            ),
            astra={"collection": collection, "documents": 0},
        )

    try:
        documents = _filtrer_corpus(_astra_lire(config, corpus), corpus)
    except Exception as erreur:
        return _resultat(
            requete, corpus, "astra", [],
            erreur="astra_indisponible",
            message="La base documentaire est momentanément injoignable.",
            astra={"collection": collection, "documents": total,
                   "detail": type(erreur).__name__},
        )

    passages = [p for p in (_passage_astra(d, corpus) for d in documents) if p["texte"]]
    trouves, ignores = _classer(requete, passages, nombre)
    message = None
    if not trouves:
        message = (
            f"Aucun passage ne correspond à la requête dans {corpus} "
            f"({len(passages)} section(s) examinée(s))."
        )
    return _resultat(
        requete, corpus, "astra", trouves,
        message=message,
        astra={"collection": collection, "documents": total,
               "candidats": len(passages)},
        ignores=ignores,
    )


# ── Point d'entrée unique ───────────────────────────────────────────
def chercher(requete: str, corpus: str = "faq", nombre: int = NOMBRE_PAR_DEFAUT) -> dict:
    if (os.environ.get("MOTEUR") or "").strip().lower() == "rag":
        try:
            from sou9na_rag.project_service import chercher_projet

            return chercher_projet(requete, corpus, nombre)
        except Exception:
            return {"passages": [], "vide": True, "citation_imposee": True,
                    "hitl": True, "erreur": "rag_indisponible"}
    nombre = _borne(nombre)
    moteur = (os.environ.get("MOTEUR") or "auto").strip().lower()
    if moteur == "vectoriel":
        moteur = "auto"

    if not corpus_valide(corpus):
        return _resultat(requete, corpus, moteur, [],
                         erreur="corpus_invalide",
                         message=f"corpus attendus : {CORPUS_STATIQUES} ou cps:<reference>")

    if corpus in CORPUS_STATIQUES:
        passages, souci = _charger_corpus(corpus)
        if passages:
            trouves, ignores = _classer(requete, passages, nombre)
            message = None if trouves else (
                f"Aucun passage ne correspond à la requête dans le corpus « {corpus} »."
            )
            return _resultat(requete, corpus, "lexical", trouves,
                             message=message, ignores=ignores)
        # corpus local absent/vide : Astra peut prendre le relais (auto/astra)
        if moteur != "lexical":
            resultat_astra = _chercher_astra(requete, corpus, nombre)
            if resultat_astra is not None:
                return resultat_astra
        message = {
            "corpus_absent": f"Corpus « {corpus} » absent : aucun fichier {corpus}.json.",
            "corpus_illisible": f"Corpus « {corpus} » illisible : vérifier le JSON.",
        }.get(souci, f"Corpus « {corpus} » vide.")
        return _resultat(requete, corpus, "lexical", [], message=message)

    # cps:<reference>
    if moteur == "lexical":
        return _resultat(
            requete, corpus, "astra", [],
            message=(
                "MOTEUR=lexical : les CPS ne sont pas indexés localement. "
                "Passer MOTEUR=auto pour interroger Astra (`sou9na`)."
            ),
        )
    resultat_astra = _chercher_astra(requete, corpus, nombre)
    if resultat_astra is None:
        return _resultat(
            requete, corpus, "astra", [],
            erreur="astra_non_configure",
            message=(
                "Astra n'est pas configuré (ASTRA_DB_API_ENDPOINT / "
                "ASTRA_DB_API_TOKEN) : aucun corpus CPS disponible."
            ),
        )
    return resultat_astra
