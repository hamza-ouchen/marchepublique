"""Accès Supabase/Postgres limité aux lectures CPS, états métier et run_logs."""

import os
from contextlib import contextmanager

import psycopg
from psycopg.rows import dict_row

from .store import BackendError


class CpsSession:
    def __init__(self, connection, document_id):
        self.connection = connection
        self.document_id = document_id

    def snapshot(self):
        doc = self.connection.execute(
            "SELECT id, reference, filename, sha256, doc_type, statut "
            "FROM public.tender_documents WHERE id = %s AND doc_type = 'CPS' FOR UPDATE",
            (self.document_id,),
        ).fetchone()
        if not doc:
            raise BackendError("CPS_DOCUMENT_NOT_FOUND")
        sections = self.connection.execute(
            "SELECT section_no, numero, titre, texte, pages_section FROM public.cps_sections "
            "WHERE document_id = %s ORDER BY section_no FOR SHARE",
            (self.document_id,),
        ).fetchall()
        return doc, sections

    def finish(self, status, reason, run_id, tokens):
        cursor = self.connection.execute(
            "UPDATE public.tender_documents SET statut = %s, echec_raison = %s, "
            "updated_at = now() WHERE id = %s AND statut IN ('extracted','ready')",
            (status, reason, self.document_id),
        )
        if cursor.rowcount != 1:
            raise BackendError("CPS_STATUS_CONFLICT")
        self.connection.execute(
            "INSERT INTO public.run_logs (run_id, type, statut, cloture_le, tokens) "
            "VALUES (%s, 'backfill', %s, now(), %s)",
            (run_id, "cloture" if status == "ready" else "echec", tokens),
        )


class CpsRepository:
    def __init__(self, dsn=None):
        self.dsn = dsn or os.environ.get("DATABASE_URL", "")
        if not self.dsn:
            raise BackendError("DATABASE_URL_REQUIRED")

    def connect(self):
        # TLS obligatoire pour la connexion distante ; pas de sortie contenant le DSN.
        return psycopg.connect(
            self.dsn, row_factory=dict_row, sslmode="require", connect_timeout=10
        )

    @contextmanager
    def session(self, document_id):
        if type(document_id) is not int or document_id < 1:
            raise BackendError("INVALID_DOCUMENT_ID")
        try:
            with self.connect() as conn:
                # REPEATABLE READ empêche un instantané mélangeant deux extractions.
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
                conn.execute("SET LOCAL lock_timeout = '5s'")
                conn.execute("SELECT pg_advisory_xact_lock(%s)", (document_id,))
                yield CpsSession(conn, document_id)
        except BackendError:
            raise
        except psycopg.Error:
            raise BackendError("SUPABASE_TRANSACTION_FAILED") from None

    def pending(self, limit=100):
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise BackendError("INVALID_BATCH_LIMIT")
        try:
            with self.connect() as conn:
                return [
                    r["id"]
                    for r in conn.execute(
                        "SELECT id FROM public.tender_documents WHERE doc_type = 'CPS' "
                        "AND statut = 'extracted' ORDER BY id LIMIT %s",
                        (limit,),
                    ).fetchall()
                ]
        except psycopg.Error:
            raise BackendError("SUPABASE_READ_FAILED") from None

    def record_regulatory_run(self, run_id, status, tokens):
        try:
            with self.connect() as conn:
                conn.execute(
                    "INSERT INTO public.run_logs (run_id, type, statut, cloture_le, tokens) "
                    "VALUES (%s, 'backfill', %s, now(), %s)",
                    (run_id, "cloture" if status == "ready" else "echec", tokens),
                )
        except psycopg.Error:
            raise BackendError("SUPABASE_LOG_FAILED") from None

    def ready_snapshots(self, reference):
        """Ne recherche jamais les chunks d'une ingestion partielle ou échouée."""
        try:
            with self.connect() as conn:
                conn.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
                docs = conn.execute(
                    "SELECT id, reference, filename, sha256, doc_type, statut "
                    "FROM public.tender_documents WHERE reference = %s "
                    "AND doc_type = 'CPS' AND statut = 'ready' ORDER BY id",
                    (reference,),
                ).fetchall()
                if len(docs) > 100:
                    raise BackendError("TOO_MANY_READY_DOCUMENTS")
                result = []
                for doc in docs:
                    sections = conn.execute(
                        "SELECT section_no, numero, titre, texte, pages_section "
                        "FROM public.cps_sections WHERE document_id = %s ORDER BY section_no",
                        (doc["id"],),
                    ).fetchall()
                    result.append((doc, sections))
                return result
        except psycopg.Error:
            raise BackendError("SUPABASE_READ_FAILED") from None
