# =====================================================================
# Accès Postgres (Supabase) pour les documents CPS — module inspecteur.
# =====================================================================
from __future__ import annotations

import os
import sys
import threading
from contextlib import closing
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

DATABASE_URL = os.getenv("DATABASE_URL", "")

# Supabase/PgBouncer impose une nouvelle connexion physique à chaque appel.
# Un pool local réutilise les connexions déjà ouvertes : c'est le principal
# levier de latence sur le dashboard et le chat (3 allers-retours → ~0 ms).
_POOL: ConnectionPool | None = None
_POOL_LOCK = threading.Lock()


class _PooledConnection:
    """Proxy rendu par connect() : close() rend la connexion au pool.

    psycopg_pool.getconn() exige putconn() (pas close()) pour réutiliser la
    connexion. Le proxy évite de modifier tous les appelants existants, y
    compris ceux qui utilisent `closing(db_cps.connect())`.
    """

    def __init__(self, conn):
        self._conn = conn
        self._rendu = False

    def __getattr__(self, nom):
        return getattr(self._conn, nom)

    def close(self):
        if self._rendu:
            return
        self._rendu = True
        if _POOL is not None:
            _POOL.putconn(self._conn)
        else:
            self._conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def connect():
    global _POOL
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL manquant")
    if _POOL is None:
        with _POOL_LOCK:
            if _POOL is None:
                _POOL = ConnectionPool(
                    conninfo=DATABASE_URL,
                    min_size=1,
                    max_size=12,
                    timeout=10.0,
                    kwargs={"row_factory": dict_row, "prepare_threshold": None},
                    open=True,
                )
    return _PooledConnection(_POOL.getconn())


def query(sql, params=()):
    conn = connect()
    try:
        return conn.execute(sql, params or None).fetchall()
    finally:
        #Une SELECT laisse la connexion INTRANS : on rend une connexion propre
        #au pool (évite les avertissements « rolling back returned connection »).
        conn.rollback()
        conn.close()


def execute(sql, params=()):
    conn = connect()
    try:
        cur = conn.execute(sql, params or None)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def query_write(sql, params=()):
    """INSERT/UPDATE ... RETURNING avec commit explicite (PgBouncer safe)."""
    conn = connect()
    try:
        lignes = conn.execute(sql, params or None).fetchall()
        conn.commit()
        return lignes
    finally:
        conn.close()


def tenders_get(reference):
    rows = query("SELECT * FROM tenders WHERE reference = %s", (reference,))
    return rows[0] if rows else None


def tender_documents_list(*, reference=None, statut=None, limit=100, offset=0):
    sql = "SELECT * FROM tender_documents WHERE 1=1"
    params = []
    if reference:
        sql += " AND reference = %s"; params.append(reference)
    if statut:
        sql += " AND statut = %s"; params.append(statut)
    sql += " ORDER BY downloaded_at DESC NULLS LAST, id DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])
    return query(sql, tuple(params))


def tender_document_by_reference(reference):
    rows = query("SELECT * FROM tender_documents WHERE reference = %s "
                 "ORDER BY (statut = 'stored'), downloaded_at DESC NULLS LAST, id DESC LIMIT 1", (reference,))
    return rows[0] if rows else None


def tender_document_create(**kw):
    cols = ", ".join(kw.keys())
    placeholders = ", ".join(["%s"] * len(kw))
    rows = query(f"INSERT INTO tender_documents ({cols}) VALUES ({placeholders}) RETURNING *",
                 tuple(kw.values()))
    return rows[0] if rows else None


def tender_document_by_hash(reference, sha256):
    rows = query(
        "SELECT * FROM tender_documents WHERE reference = %s AND sha256 = %s",
        (reference, sha256),
    )
    return rows[0] if rows else None


def save_document_version(document_sections, **fields):
    columns = ", ".join(fields)
    values = ", ".join(["%s"] * len(fields))
    updates = ", ".join(
        f"{column} = EXCLUDED.{column}" for column in fields
        if column not in ("reference", "sha256")
    )
    with closing(connect()) as conn:
        try:
            with conn.transaction():
                document = conn.execute(
                    f"INSERT INTO tender_documents ({columns}) VALUES ({values}) "
                    f"ON CONFLICT (reference, sha256) DO UPDATE SET {updates}, updated_at = now() "
                    "WHERE EXCLUDED.statut <> 'echec' OR tender_documents.statut NOT IN ('extracted','ready') "
                    "RETURNING *",
                    tuple(fields.values()),
                ).fetchone()
                if document is None:
                    return conn.execute(
                        "SELECT * FROM tender_documents WHERE reference = %s AND sha256 = %s",
                        (fields["reference"], fields["sha256"]),
                    ).fetchone()
                document_id = document["id"]
                conn.execute("DELETE FROM cps_sections WHERE document_id = %s", (document_id,))
                with conn.cursor() as cursor:
                    cursor.executemany(
                        "INSERT INTO cps_sections (document_id, section_no, numero, titre, texte, pages_section) "
                        "VALUES (%s,%s,%s,%s,%s,%s)",
                        [(document_id, s["section_no"], s.get("numero"), s.get("titre"),
                          s["texte"], s.get("pages_section")) for s in document_sections],
                    )
                return document
        except psycopg.errors.UniqueViolation:
            existing = conn.execute(
                "SELECT * FROM tender_documents WHERE reference = %s AND sha256 = %s",
                (fields["reference"], fields["sha256"]),
            ).fetchone()
            if existing is None:
                raise
            return existing


def tender_document_update_status(doc_id, statut, echec_raison=None, sections=None,
                                  char_count=None, extraction=None):
    sets = ["statut = %s", "updated_at = now()"]
    params = [statut]
    if echec_raison is not None:
        sets.append("echec_raison = %s"); params.append(echec_raison)
    if sections is not None:
        sets.append("sections = %s"); params.append(sections)
    if char_count is not None:
        sets.append("char_count = %s"); params.append(char_count)
    if extraction is not None:
        sets.append("extraction = %s"); params.append(extraction)
    params.append(doc_id)
    execute(f"UPDATE tender_documents SET {', '.join(sets)} WHERE id = %s", tuple(params))


def tender_document_mark_ready(doc_id):
    execute("UPDATE tender_documents SET statut = 'ready', updated_at = now() "
            "WHERE id = %s AND statut IN ('extracted','ready')", (doc_id,))


def cps_sections_replace(document_id, sections):
    execute("DELETE FROM cps_sections WHERE document_id = %s", (document_id,))
    n = 0
    for s in sections:
        execute("INSERT INTO cps_sections (document_id, section_no, numero, titre, texte, pages_section) "
                "VALUES (%s,%s,%s,%s,%s,%s)",
                (document_id, s["section_no"], s.get("numero"), s.get("titre"),
                 s["texte"], s.get("pages_section")))
        n += 1
    return n


def cps_status(reference):
    doc = tender_document_by_reference(reference)
    if not doc:
        return {"reference": reference, "has_document": False, "statut": "missing_cps",
                "document_id": None, "sections": 0, "char_count": 0,
                "downloaded_at": None, "updated_at": None}
    rows = query("SELECT count(*) AS n FROM cps_sections WHERE document_id = %s", (doc["id"],))
    secs = rows[0]["n"] if rows else 0
    return {
        "reference": reference,
        "has_document": True,
        "document_id": doc["id"],
        "doc_type": doc.get("doc_type"),
        "statut": doc.get("statut"),
        "sections": secs if secs else (doc.get("sections") or 0),
        "char_count": doc.get("char_count"),
        "pages": doc.get("pages"),
        "extraction": doc.get("extraction"),
        "echec_raison": doc.get("echec_raison"),
        "downloaded_at": doc.get("downloaded_at"),
        "updated_at": doc.get("updated_at"),
        "source_url": doc.get("source_url"),
    }
