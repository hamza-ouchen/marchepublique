# =====================================================================
# Accès Postgres pour le JUGE (verdicts).
# =====================================================================
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import psycopg
from psycopg.rows import dict_row

_ROOT = Path(__file__).resolve().parents[2]
_ENV = _ROOT / "02-backend" / ".env"


def _load_env() -> None:
    if not _ENV.exists():
        return
    for line in _ENV.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_env()


def get_conn():
    return psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row,
                           prepare_threshold=None)


_CACHE: dict[str, Any] = {}
_WRITE_CONN = None


def scores_for_date(date: str, company: str | None = None) -> list[dict[str, Any]]:
    with get_conn() as conn, conn.cursor() as cur:
        cur.execute(
            "SELECT company_id, reference, match_total, composantes, algo_version "
            "FROM scores WHERE calcule_le::date = %s"
            + (" AND company_id = %s" if company else ""),
            (date, company) if company else (date,),
        )
        return cur.fetchall()


def _sections_index() -> dict[str, dict[str, Any]]:
    """Une seule requête pour toute la journée, puis index par référence."""
    if "sections" not in _CACHE:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT DISTINCT ON (d.reference)
                       d.reference, d.filename, d.source_url, s.numero, s.pages_section
                FROM tender_documents d JOIN cps_sections s ON s.document_id = d.id
                WHERE d.statut IN ('extracted', 'ready')
                  AND (s.texte ILIKE ANY(%s) OR s.titre ILIKE ANY(%s))
                ORDER BY d.reference, d.downloaded_at DESC NULLS LAST,
                         d.id DESC, s.section_no
                """,
                (["%qualification%", "%agrément%", "%مؤهلات%"],
                 ["%qualification%", "%agrément%", "%مؤهلات%"]),
            )
            _CACHE["sections"] = {r["reference"]: r for r in cur.fetchall()}
    return _CACHE["sections"]


def qualification_section(reference: str) -> dict[str, Any] | None:
    return _sections_index().get(reference)


def doc_index() -> dict[str, dict[str, Any]]:
    """Une requête pour savoir, par référence, si un dossier est exploitable."""
    if "docs" not in _CACHE:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT d.reference,
                       true AS has_doc,
                       COUNT(DISTINCT d.id) AS nb_documents,
                       COUNT(s.id) AS nb_sections
                FROM tender_documents d
                LEFT JOIN cps_sections s ON s.document_id = d.id
                WHERE d.statut IN ('extracted', 'ready')
                  AND (d.char_count > 0 OR d.sections > 0
                       OR NULLIF(btrim(d.extracted_text), '') IS NOT NULL)
                GROUP BY d.reference
                """
            )
            _CACHE["docs"] = {r["reference"]: r for r in cur.fetchall()}
    return _CACHE["docs"]


def tender_by_reference(reference: str) -> dict[str, Any] | None:
    """Cache collectif : une seule requête pour toutes les annonces."""
    if "tenders" not in _CACHE:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM tenders")
            _CACHE["tenders"] = {r["reference"]: r for r in cur.fetchall()}
    return _CACHE["tenders"].get(reference)


def entreprise_by_id(company_id: str) -> dict[str, Any] | None:
    if company_id not in _CACHE:
        with get_conn() as conn, conn.cursor() as cur:
            cur.execute("SELECT * FROM company_matching_profiles WHERE company_id = %s", (company_id,))
            _CACHE[company_id] = cur.fetchone()
    return _CACHE[company_id]


def upsert_verdict(row: dict[str, Any]) -> None:
    """Une seule connexion en écriture (autocommit) pour tout le lot."""
    global _WRITE_CONN
    if _WRITE_CONN is None or _WRITE_CONN.closed:
        # Une seule transaction pour tout le lot (au lieu d'un commit par
        # verdict) : c'est ce qui faisait dépasser le délai A2A du JUGE.
        _WRITE_CONN = psycopg.connect(os.environ["DATABASE_URL"],
                                      prepare_threshold=None)
    with _WRITE_CONN.cursor() as cur:
        cur.execute(
            """
            INSERT INTO verdicts
              (company_id, reference, verdict, controles, justifications, risques_a_verifier, rendu_le)
            VALUES
              (%(company_id)s, %(reference)s, %(verdict)s, %(controles)s::jsonb,
               %(justifications)s::jsonb, %(risques)s::jsonb, now())
            ON CONFLICT (company_id, reference) DO UPDATE SET
              verdict = EXCLUDED.verdict,
              controles = EXCLUDED.controles,
              justifications = EXCLUDED.justifications,
              risques_a_verifier = EXCLUDED.risques_a_verifier,
              rendu_le = now()
            """,
            {
                "company_id": row["company_id"],
                "reference": row["reference"],
                "verdict": row["verdict"],
                "controles": __import__("json").dumps(row["controles"]),
                "justifications": __import__("json").dumps(row["justifications"]),
                "risques": __import__("json").dumps(row["risques_a_verifier"]),
            },
        )


def commit_verdicts() -> None:
    """Valide le lot complet en une seule transaction."""
    global _WRITE_CONN
    if _WRITE_CONN is not None and not _WRITE_CONN.closed:
        _WRITE_CONN.commit()
