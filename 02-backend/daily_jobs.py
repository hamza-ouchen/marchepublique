"""Persistent jobs shared by FastAPI and the daily workflow worker."""
from __future__ import annotations

import os
import sys
from contextlib import closing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "04-langgraph" / "inspecteur"))
import db_cps

_MOROCCO_DATE = "(now() at time zone 'Africa/Casablanca')::date"
_SCHEMA_READY = False


def _ensure_schema() -> None:
    """Ajoute les colonnes de mode/collecte si la table vient d'une ancienne version."""
    global _SCHEMA_READY
    if _SCHEMA_READY:
        return
    db_cps.execute(
        "ALTER TABLE public.daily_workflow_jobs "
        "ADD COLUMN IF NOT EXISTS mode text NOT NULL DEFAULT 'auto'"
    )
    db_cps.execute(
        "ALTER TABLE public.daily_workflow_jobs "
        "ADD COLUMN IF NOT EXISTS collecte text NOT NULL DEFAULT 'auto'"
    )
    _SCHEMA_READY = True


def company_statuses() -> list[str]:
    """Statuts éligibles au cycle quotidien (configurables en production)."""
    brut = os.getenv("SOU9NA_COMPANY_STATUSES", "actif,essai")
    return [s.strip() for s in brut.split(",") if s.strip()] or ["actif"]


def list_companies(*, statuses: list[str] | None = None,
                   limit: int | None = None, offset: int = 0) -> list[str]:
    """Toutes les entreprises à traiter — pas un seul company_id en dur."""
    statuses = statuses if statuses is not None else company_statuses()
    sql = (
        "SELECT company_id FROM public.company_matching_profiles "
        "WHERE statut = ANY(%s) ORDER BY company_id"
    )
    params: list = [statuses]
    if limit:
        sql += " LIMIT %s OFFSET %s"
        params.extend([limit, max(0, offset)])
    rows = db_cps.query(sql, tuple(params))
    return [r["company_id"] for r in rows]


def enqueue(company: str, mode: str = "auto", collecte: str = "auto") -> dict:
    _ensure_schema()
    with closing(db_cps.connect()) as conn, conn.transaction():
        job = conn.execute(
            f"""
            INSERT INTO public.daily_workflow_jobs (run_date, company_id, mode, collecte)
            VALUES ({_MOROCCO_DATE}, %s, %s, %s)
            ON CONFLICT (run_date, company_id)
            DO UPDATE SET mode = EXCLUDED.mode, collecte = EXCLUDED.collecte
            RETURNING *
            """,
            (company, mode, collecte),
        ).fetchone()
        if job:
            return job
        return conn.execute(
            f"SELECT * FROM public.daily_workflow_jobs "
            f"WHERE run_date = {_MOROCCO_DATE} AND company_id = %s",
            (company,),
        ).fetchone()


def enqueue_many(companies: list[str], mode: str = "auto",
                 collecte: str = "auto") -> list[dict]:
    """Une seule inscription groupée pour 1000 entreprises."""
    if not companies:
        return []
    _ensure_schema()
    with closing(db_cps.connect()) as conn, conn.transaction():
        return conn.execute(
            f"""
            INSERT INTO public.daily_workflow_jobs (run_date, company_id, mode, collecte)
            SELECT {_MOROCCO_DATE}, c.company_id, %s, %s
            FROM unnest(%s::text[]) AS c(company_id)
            ON CONFLICT (run_date, company_id)
            DO UPDATE SET mode = EXCLUDED.mode, collecte = EXCLUDED.collecte
            RETURNING *
            """,
            (mode, collecte, companies),
        ).fetchall()


def latest() -> dict | None:
    rows = db_cps.query(
        "SELECT * FROM public.daily_workflow_jobs ORDER BY queued_at DESC LIMIT 1"
    )
    return rows[0] if rows else None


def recover_stale(hours: int = 2) -> int:
    """Un worker tombé ne doit pas bloquer la file pour toujours."""
    with closing(db_cps.connect()) as conn, conn.transaction():
        cur = conn.execute(
            """
            UPDATE public.daily_workflow_jobs
            SET state = 'queued', started_at = NULL
            WHERE state = 'running'
              AND (started_at IS NULL OR started_at < now() - make_interval(hours => %s))
            """,
            (hours,),
        )
        return cur.rowcount or 0


def claim() -> dict | None:
    with closing(db_cps.connect()) as conn, conn.transaction():
        # Serialize claims across worker processes. The running row stays
        # visible after commit and prevents another job using scraper files.
        conn.execute("SELECT pg_advisory_xact_lock(610071307)")
        recover_stale(int(os.getenv("SOU9NA_STALE_JOB_HOURS", "2")))
        return conn.execute(
            """
            UPDATE public.daily_workflow_jobs
            SET state = 'running', started_at = now()
            WHERE (run_date, company_id) = (
                SELECT run_date, company_id
                FROM public.daily_workflow_jobs
                WHERE state = 'queued'
                ORDER BY queued_at, run_date, company_id
                LIMIT 1
            )
            AND NOT EXISTS (
                SELECT 1 FROM public.daily_workflow_jobs WHERE state = 'running'
            )
            RETURNING *
            """
        ).fetchone()


def finish(job: dict, exit_code: int) -> None:
    db_cps.execute(
        """
        UPDATE public.daily_workflow_jobs
        SET state = %s, finished_at = now(), exit_code = %s
        WHERE run_date = %s AND company_id = %s AND state = 'running'
        """,
        ("succeeded" if exit_code == 0 else "failed", exit_code,
         job["run_date"], job["company_id"]),
    )


def mark_init(company: str, status: str, error: str | None = None) -> None:
    """Pilote l'écran d'attente premium de l'entreprise."""
    if status == "running":
        db_cps.execute(
            """
            UPDATE public.companies
            SET init_status = 'running', init_started_at = now(), init_error = NULL
            WHERE company_id = %s
            """, (company,),
        )
    elif status == "ready":
        db_cps.execute(
            """
            UPDATE public.companies
            SET init_status = 'ready', init_error = NULL
            WHERE company_id = %s
            """, (company,),
        )
    elif status == "error":
        db_cps.execute(
            """
            UPDATE public.companies
            SET init_status = 'error', init_error = %s
            WHERE company_id = %s AND init_status = 'running'
            """, ((error or "")[:240], company),
        )
