# =====================================================================
# Accès Postgres (Supabase) pour les documents CPS — module inspecteur.
# =====================================================================
from __future__ import annotations

import os
import sys
from typing import Any

import psycopg
from psycopg.rows import dict_row

DATABASE_URL = os.getenv("DATABASE_URL", "")


def connect():
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL manquant")
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def query(sql, params=()):
    conn = connect()
    try:
        return conn.execute(sql, params or None).fetchall()
    finally:
        conn.close()


def execute(sql, params=()):
    conn = connect()
    try:
        cur = conn.execute(sql, params or None)
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def tenders_get(reference):
    rows = query("SELECT * FROM tenders WHERE reference = %s", (reference,))
    return rows[0] if rows else None


def tender_document_by_reference(reference):
    rows = query("SELECT * FROM tender_documents WHERE reference = %s "
                 "ORDER BY downloaded_at DESC NULLS LAST, id DESC LIMIT 1", (reference,))
    return rows[0] if rows else None


def tender_document_create(**kw):
    cols = ", ".join(kw.keys())
    placeholders = ", ".join(["%s"] * len(kw))
    rows = query(f"INSERT INTO tender_documents ({cols}) VALUES ({placeholders}) RETURNING *",
                 tuple(kw.values()))
    return rows[0] if rows else None


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