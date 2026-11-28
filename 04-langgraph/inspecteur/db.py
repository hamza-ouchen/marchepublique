# =====================================================================
# Accès Postgres/Supabase pour la collecte de documents.
# - sélection des avis pertinents (tenders + profils clients)
# - écriture idempotente des documents et sections (005_cps.sql)
# =====================================================================
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

_pool: ConnectionPool | None = None

SCHEMA_SQL = """
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS tender_documents (
    id            BIGSERIAL PRIMARY KEY,
    reference     TEXT NOT NULL REFERENCES tenders(reference) ON DELETE CASCADE,
    doc_type      TEXT CHECK (doc_type IN ('CPS','DCE','AVIS','ADDITIF','PV')),
    filename      TEXT,
    mime          TEXT,
    storage_path  TEXT,
    sha256        TEXT NOT NULL UNIQUE,
    size_bytes    BIGINT,
    pages         INTEGER,
    extraction    TEXT,
    extracted_text TEXT,
    source_url    TEXT,
    request_id    TEXT,
    downloaded_at TIMESTAMPTZ,
    statut        TEXT NOT NULL CHECK (statut IN
                  ('downloading','extracted','ready','echec','missing_cps')),
    echec_raison  TEXT,
    sections      INTEGER CHECK (sections IS NULL OR sections >= 0),
    char_count    INTEGER CHECK (char_count IS NULL OR char_count >= 0),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tender_documents_reference
    ON tender_documents(reference);
CREATE INDEX IF NOT EXISTS idx_tender_documents_statut
    ON tender_documents(statut);

CREATE TABLE IF NOT EXISTS cps_sections (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  BIGINT NOT NULL REFERENCES tender_documents(id) ON DELETE CASCADE,
    section_no   INTEGER NOT NULL CHECK (section_no > 0),
    numero       TEXT,
    titre        TEXT,
    texte        TEXT NOT NULL CHECK (length(trim(texte)) > 0),
    pages_section TEXT,
    cree_le      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, section_no)
);

CREATE INDEX IF NOT EXISTS idx_cps_sections_document
    ON cps_sections(document_id);
"""


def connect() -> psycopg.Connection:
    """Connexion compatible pooler transactionnel Supabase (pgbouncer)."""
    global _pool
    if not config.DATABASE_URL:
        raise RuntimeError("DATABASE_URL manquant (copier .env.example vers .env)")
    if _pool is None:
        _pool = ConnectionPool(
            config.DATABASE_URL,
            min_size=1,
            max_size=5,
            open=True,
            kwargs={
                "autocommit": True,
                "prepare_threshold": None,
                "row_factory": dict_row,
            },
        )
    return _pool.getconn()


def putconn(conn: psycopg.Connection) -> None:
    if _pool is not None:
        _pool.putconn(conn)


def query(sql: str, params: tuple | list | None = None) -> list[dict[str, Any]]:
    conn = connect()
    try:
        rows = conn.execute(sql, params or None).fetchall()
        return [dict(r) for r in rows]
    finally:
        putconn(conn)


def execute(sql: str, params: tuple | list | None = None) -> None:
    conn = connect()
    try:
        conn.execute(sql, params or None)
    finally:
        putconn(conn)


def close() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


def ensure_schema() -> None:
    """Crée les tables de documents si les migrations 005/006 ne sont pas appliquées."""
    conn = connect()
    try:
        for statement in filter(None, (s.strip() for s in SCHEMA_SQL.split(";"))):
            conn.execute(statement + ";")
    finally:
        putconn(conn)


# -----------------------------------------------------------------------
# Cible : profils clients actifs
# -----------------------------------------------------------------------

def active_profiles() -> list[dict[str, Any]]:
    """Profils des clients actifs (schéma officiel 'entreprises', repli 'companies')."""
    try:
        rows = query(
            "SELECT secteur, region, capacite_mad FROM company_matching_profiles "
            "WHERE lower(coalesce(statut,'actif')) IN ('actif','essai')"
        )
        if rows:
            return rows
    except Exception:
        pass
    try:
        rows = query("SELECT * FROM companies WHERE lower(coalesce(status,'active')) "
                     "IN ('active','trial','essai','actif')")
        out: list[dict[str, Any]] = []
        for r in rows:
            sectors = r.get("sectors") or []
            regions = r.get("regions") or []
            capacity = r.get("budget_max") or r.get("capacite_mad") or 0
            for s in sectors:
                for rg in regions or [""]:
                    out.append({"secteur": s, "region": rg, "capacite_mad": capacity})
            if not sectors:
                out.append({"secteur": r.get("sector") or "", "region": "",
                            "capacite_mad": capacity})
        return out
    except Exception:
        return []


# -----------------------------------------------------------------------
# Candidats
# -----------------------------------------------------------------------

def candidate_tenders(limit: int = 500) -> list[dict[str, Any]]:
    """Avis encore actionnables, sans document déjà ingéré, les plus proches d'abord."""
    return query(
        """
        SELECT t.reference, t.source_url, t.secteur, t.region,
               t.montant_mad, t.date_remise, t.statut
        FROM tenders t
        WHERE (t.date_remise IS NULL OR t.date_remise >= CURRENT_DATE)
          AND NOT EXISTS (
              SELECT 1 FROM tender_documents td
              WHERE td.reference = t.reference
                AND td.statut IN ('extracted','ready')
          )
        ORDER BY t.date_remise ASC NULLS LAST, t.reference ASC
        LIMIT %s
        """,
        (limit,),
    )


def document_for(reference: str) -> dict[str, Any] | None:
    rows = query(
        "SELECT id, statut, sha256 FROM tender_documents WHERE reference = %s "
        "ORDER BY downloaded_at DESC NULLS LAST, id DESC LIMIT 1",
        (reference,),
    )
    return rows[0] if rows else None


def sha_exists(sha256: str) -> bool:
    rows = query("SELECT 1 FROM tender_documents WHERE sha256 = %s LIMIT 1", (sha256,))
    return bool(rows)


def update_tender_publication_date(reference: str, pub_date: str) -> None:
    """Renseigne tenders.date_publication si elle est absente."""
    try:
        execute(
            "UPDATE tenders SET date_publication = COALESCE(date_publication, %s::date), "
            "mis_a_jour_le = now() WHERE reference = %s",
            (pub_date, reference),
        )
    except Exception:
        pass


def usage_bytes() -> int:
    """Octets des originaux déjà suivis en base (proxy du budget storage)."""
    rows = query("SELECT COALESCE(sum(size_bytes),0) AS n FROM tender_documents")
    return int(rows[0]["n"] or 0) if rows else 0


# -----------------------------------------------------------------------
# Écritures
# -----------------------------------------------------------------------

def insert_document(**d: Any) -> int:
    rows = query(
        """
        INSERT INTO tender_documents (
            reference, doc_type, filename, mime, storage_path, sha256,
            size_bytes, pages, extraction, extracted_text, source_url,
            request_id, downloaded_at, statut, echec_raison, sections, char_count)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (sha256) DO UPDATE SET
            reference=EXCLUDED.reference, storage_path=EXCLUDED.storage_path,
            size_bytes=EXCLUDED.size_bytes, pages=EXCLUDED.pages,
            extraction=EXCLUDED.extraction, extracted_text=EXCLUDED.extracted_text,
            source_url=EXCLUDED.source_url, request_id=EXCLUDED.request_id,
            downloaded_at=EXCLUDED.downloaded_at, statut=EXCLUDED.statut,
            echec_raison=EXCLUDED.echec_raison, sections=EXCLUDED.sections,
            char_count=EXCLUDED.char_count, updated_at=now()
        RETURNING id
        """,
        (
            d["reference"], d.get("doc_type", "CPS"), d.get("filename"),
            d.get("mime", "application/pdf"), d["storage_path"], d["sha256"],
            d.get("size_bytes"), d.get("pages"), d.get("extraction"),
            d.get("extracted_text"), d.get("source_url"), d.get("request_id"),
            d.get("downloaded_at") or datetime.now(timezone.utc),
            d.get("statut", "extracted"), d.get("echec_raison"),
            d.get("sections"), d.get("char_count"),
        ),
    )
    if not rows:
        raise RuntimeError("insert tender_documents: aucune ligne retournée")
    return int(rows[0]["id"])


def replace_sections(document_id: int, sections: list[dict[str, Any]]) -> int:
    execute("DELETE FROM cps_sections WHERE document_id = %s AND COALESCE(to_jsonb(cps_sections)->'legacy_sections','[]'::jsonb) = '[]'::jsonb", (document_id,))
    for s in sections:
        execute(
            "INSERT INTO cps_sections (document_id, section_no, numero, titre, texte, "
            "pages_section) VALUES (%s,%s,%s,%s,%s,%s) ON CONFLICT (document_id, section_no) DO NOTHING",
            (document_id, s["section_no"], s.get("numero"), s.get("titre"),
             s["texte"], s.get("pages_section")),
        )
    return len(sections)


# -----------------------------------------------------------------------
# Job complet : offres (tenders), statuts réels, champs riches
# -----------------------------------------------------------------------

def offer_exists(reference: str) -> bool:
    return bool(query("SELECT 1 FROM tenders WHERE reference = %s LIMIT 1",
                      (reference,)))


def offer_type_from_reference(reference: str, source_url: str | None = None) -> str:
    """Nature de l'avis : appel d'offres / consultation / bon de commande."""
    indice = f"{reference or ''} {source_url or ''}".lower()
    if "bdc:" in indice or "/bdc/" in indice or "bon-de-commande" in indice:
        return "bon_de_commande"
    if "consultation:" in indice or "refconsultation=" in indice or "consultation/" in indice:
        return "consultation"
    return "appel_offres"


def upsert_offer(*, reference: str, organisme: str, objet: str, secteur: str,
                  region: str, montant_mad: float | None, date_remise: Any,
                  statut: str, source_url: str, date_collecte: Any,
                  offer_type: str | None = None) -> None:
    """Upsert idempotent d'une offre du listing portail."""
    nature = offer_type or offer_type_from_reference(reference, source_url)
    execute(
        """
        INSERT INTO tenders (reference, organisme, objet, secteur, region,
                             montant_mad, caution_mad, lots, qualifications_exigees,
                             delai_jours, date_publication, date_remise, date_collecte,
                             statut, source, source_url, offer_type, cree_le, mis_a_jour_le)
        VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,0,NULL,%s,%s,%s,'portail',%s,%s,now(),NULL)
        ON CONFLICT (reference) DO UPDATE SET
            organisme=EXCLUDED.organisme, objet=EXCLUDED.objet,
            secteur=EXCLUDED.secteur, region=EXCLUDED.region,
            montant_mad=EXCLUDED.montant_mad,
            date_remise=EXCLUDED.date_remise, date_collecte=EXCLUDED.date_collecte,
            statut=EXCLUDED.statut, source_url=EXCLUDED.source_url,
            offer_type=EXCLUDED.offer_type,
            mis_a_jour_le=now()
        """,
        (reference, organisme, objet, secteur, region, montant_mad,
         [], [], date_remise, date_collecte, statut, source_url, nature),
    )


def delete_offer(reference: str) -> None:
    """Supprime une offre terminée : scores/verdicts d'abord (FK sans
    cascade), documents en cascade via tender_documents."""
    execute("DELETE FROM scores WHERE reference = %s", (reference,))
    execute("DELETE FROM verdicts WHERE reference = %s", (reference,))
    execute("DELETE FROM tenders WHERE reference = %s", (reference,))


def tenders_missing_deadline(limit: int = 100000) -> list[dict[str, Any]]:
    """Offres ouvertes sans deadline connue (statut réel à vérifier)."""
    return query(
        """
        SELECT reference, source_url FROM tenders
        WHERE statut = 'ouvert' AND date_remise IS NULL
          AND source_url LIKE '%%refConsultation=%%'
        ORDER BY cree_le DESC LIMIT %s
        """,
        (limit,),
    )


def set_tender_deadline(reference: str, deadline: Any) -> None:
    """Deadline réelle lue sur la page de détail (offre ouverte)."""
    execute(
        "UPDATE tenders SET date_remise = %s, statut = 'ouvert', "
        "mis_a_jour_le = now() WHERE reference = %s",
        (deadline, reference),
    )


def update_tender_fields(reference: str, fields: dict[str, Any]) -> None:
    """Champs riches déduits du texte CPS/RC (montant, caution, lots,
    qualifications, délai). Ne touche que les clés fournies."""
    sets, params = [], []
    for key, value in fields.items():
        sets.append(f"{key} = %s")
        params.append(value)
    if not sets:
        return
    params.append(reference)
    execute(f"UPDATE tenders SET {', '.join(sets)}, mis_a_jour_le = now() "
            "WHERE reference = %s", tuple(params))


def offers_missing_fields(limit: int = 500) -> list[dict[str, Any]]:
    """Offres ouvertes avec documents extraits et champs riches incomplets."""
    return query(
        """
        SELECT DISTINCT t.reference, t.montant_mad, t.caution_mad, t.lots,
               t.qualifications_exigees, t.delai_jours
        FROM tenders t
        JOIN tender_documents d ON d.reference = t.reference
        WHERE t.statut = 'ouvert'
          AND d.statut = 'extracted'
          AND d.extracted_text IS NOT NULL
          AND length(d.extracted_text) > 200
          AND (t.montant_mad IS NULL OR t.caution_mad IS NULL
               OR t.lots = '{}' OR t.lots IS NULL
               OR t.qualifications_exigees = '{}' OR t.qualifications_exigees IS NULL
               OR t.delai_jours IS NULL OR t.delai_jours = 0)
        LIMIT %s
        """,
        (limit,),
    )


def documents_texts(reference: str) -> list[dict[str, Any]]:
    """Textes extraits des documents d'une offre (CPS prioritaire)."""
    return query(
        "SELECT doc_type, extracted_text FROM tender_documents "
        "WHERE reference = %s AND statut = 'extracted' "
        "AND extracted_text IS NOT NULL",
        (reference,),
    )


def offers_without_documents(limit: int = 60) -> list[dict[str, Any]]:
    """Offres ouvertes sans document ingéré, échéance la plus proche d'abord."""
    return query(
        """
        SELECT t.reference, t.source_url, t.date_remise FROM tenders t
        WHERE t.statut = 'ouvert'
          AND t.source_url LIKE '%%refConsultation=%%'
          AND t.source_url LIKE '%%orgAcronyme=%%'
          AND NOT EXISTS (
              SELECT 1 FROM tender_documents d
              WHERE d.reference = t.reference
                AND d.statut IN ('extracted', 'ready'))
        ORDER BY (t.date_remise IS NULL), t.date_remise ASC NULLS LAST,
                 t.cree_le DESC
        LIMIT %s
        """,
        (limit,),
    )
