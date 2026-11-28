"""Load the audited CPS gaps and merge documents in resumable batches."""

import argparse
import csv
import gzip
import json
import os
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory

from dotenv import load_dotenv
import psycopg
from psycopg.types.json import Jsonb


BACKEND = Path(__file__).resolve().parents[1]
AUDIT_TABLES = ("cps_sections2", "cps_sections_3")

MAKE_CANDIDATES = """
CREATE TEMP TABLE cps_candidates ON COMMIT DROP AS
SELECT d.id AS document_id, x.item->>'texte' AS texte,
       min(nullif(x.item->>'numero','')) AS numero,
       min(nullif(x.item->>'titre','')) AS titre,
       min(nullif(x.item->>'pages_section','')) AS pages_section,
       jsonb_agg(DISTINCT jsonb_build_object('origin',x.origin,'row',
           x.item - 'texte' - 'audit_reason' - 'canonical_document_id')) AS history
FROM cps_archive_input x
JOIN public.tender_documents d ON d.reference=x.reference AND d.sha256=x.sha256
WHERE nullif(trim(x.item->>'texte'),'') IS NOT NULL
GROUP BY d.id,x.item->>'texte';
"""

SAVE_SECTIONS = """
CREATE TEMP TABLE cps_existing ON COMMIT DROP AS
SELECT m.*,s.id
FROM cps_candidates m LEFT JOIN LATERAL (
    SELECT id FROM public.cps_sections s
    WHERE s.document_id=m.document_id AND s.texte=m.texte
    ORDER BY s.section_no,s.id LIMIT 1
) s ON true;

UPDATE public.cps_sections s
SET legacy_sections=(
    SELECT jsonb_agg(DISTINCT entry)
    FROM jsonb_array_elements(s.legacy_sections||x.history) entry
)
FROM cps_existing x
WHERE s.id=x.id AND NOT s.legacy_sections @> x.history;

WITH pending AS (
    SELECT x.*,row_number() OVER (PARTITION BY document_id ORDER BY sha256(convert_to(texte,'UTF8'))) AS offset_no
    FROM cps_existing x WHERE id IS NULL
), max_sections AS (
    SELECT s.document_id,max(s.section_no) AS last_no
    FROM public.cps_sections s JOIN (SELECT DISTINCT document_id FROM pending) d USING(document_id)
    GROUP BY s.document_id
)
INSERT INTO public.cps_sections(document_id,section_no,numero,titre,texte,pages_section,legacy_sections)
SELECT p.document_id,coalesce(m.last_no,0)+p.offset_no,p.numero,p.titre,p.texte,p.pages_section,p.history
FROM pending p LEFT JOIN max_sections m USING(document_id);

WITH needed AS (
    SELECT d.id AS document_id, x.item->>'texte' AS texte, array_agg(DISTINCT topic) AS topics
    FROM cps_archive_input x
    JOIN public.tender_documents d ON (d.reference,d.sha256)=(x.reference,x.sha256)
    CROSS JOIN LATERAL unnest(nullif(x.item->>'sujets','')::text[]) AS topic
    GROUP BY 1,2
), chosen AS (
    SELECT s.id,n.topics FROM needed n
    CROSS JOIN LATERAL (
      SELECT id FROM public.cps_sections s WHERE s.document_id=n.document_id AND s.texte=n.texte
      ORDER BY s.section_no,s.id LIMIT 1
    ) s
)
UPDATE public.cps_sections s
SET sujets=ARRAY(SELECT DISTINCT item FROM unnest(s.sujets||x.topics) item ORDER BY item)
FROM chosen x WHERE x.id=s.id AND NOT s.sujets @> x.topics;
"""

CHECK_SECTIONS = """
SELECT count(*) FROM cps_archive_input x
LEFT JOIN public.tender_documents d ON (d.reference,d.sha256)=(x.reference,x.sha256)
WHERE nullif(trim(x.item->>'texte'),'') IS NOT NULL
AND NOT EXISTS (
    SELECT 1 FROM public.cps_sections s
    WHERE s.document_id=d.id AND s.texte=x.item->>'texte'
      AND s.sujets @> coalesce(nullif(x.item->>'sujets','')::text[],'{}')
)
"""


def load_audit(index: sqlite3.Connection, folder: Path) -> None:
    csv.field_size_limit(100_000_000)
    report = json.loads((folder / "cps-gap-audit.json").read_text(encoding="utf-8"))
    index.execute("CREATE TABLE entries (reference TEXT, sha TEXT, origin TEXT, payload TEXT)")
    for table in AUDIT_TABLES:
        stats = report[table]
        expected = stats["rows_archived"] - stats["rows_already_covered"]
        with gzip.open(folder / stats["report"], "rt", encoding="utf-8", newline="") as stream:
            records = (
                (row["reference"], row["sha256"], table, json.dumps(row, ensure_ascii=False))
                for row in csv.DictReader(stream)
            )
            inserted = index.executemany("INSERT INTO entries VALUES(?,?,?,?)", records).rowcount
        if inserted != expected:
            raise RuntimeError(f"Audit rows changed for {table}")
    index.execute("CREATE INDEX entries_reference ON entries(reference)")
    index.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--batch-size", type=int, default=45)
    parser.add_argument("--resume-offset", type=int, default=0,
                        help="Continue after a previously committed count of sorted references.")
    parser.add_argument("--retire-legacy", action="store_true")
    args = parser.parse_args()
    if args.batch_size < 1 or args.resume_offset < 0:
        parser.error("Batch size must be positive and resume offset nonnegative")
    load_dotenv(BACKEND / ".env")
    migration = (BACKEND / "migrations/022_consolidate_tender_documents.sql").read_text(encoding="utf-8")
    document_sql = migration.split("-- MERGE BATCH", 1)[1].split("CREATE TEMP TABLE merged_sections", 1)[0]
    with TemporaryDirectory(prefix="sou9na-cps-import-") as temp:
        index = sqlite3.connect(Path(temp) / "cps.sqlite3")
        try:
            load_audit(index, args.archive)
            with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True, connect_timeout=8) as conn:
                if conn.execute("SELECT to_regclass('public.tender_documents_duplicate')").fetchone()[0] is None:
                    print("Legacy document table already retired.")
                    return
                if conn.execute("SHOW transaction_read_only").fetchone()[0] != "off":
                    raise RuntimeError("PostgreSQL is read-only")
                conn.execute("SET lock_timeout='6s'")
                conn.execute("SET statement_timeout='90s'")
                refs = {row[0] for row in conn.execute("SELECT DISTINCT reference FROM tender_documents_duplicate")}
                refs.update(row[0] for row in index.execute("SELECT DISTINCT reference FROM entries"))
                ordered = sorted(refs)
                for i in range(args.resume_offset, len(ordered), args.batch_size):
                    scope = ordered[i:i + args.batch_size]
                    with conn.transaction():
                        conn.execute("CREATE TEMP TABLE merge_scope(reference text PRIMARY KEY) ON COMMIT DROP")
                        conn.execute("INSERT INTO merge_scope SELECT unnest(%s::text[])", (scope,))
                        conn.execute(document_sql)
                        conn.execute("""CREATE TEMP TABLE cps_archive_input(
                          reference text,sha256 text,origin text,item jsonb) ON COMMIT DROP""")
                        with conn.cursor().copy("COPY cps_archive_input FROM STDIN") as copy:
                            marks = ",".join("?" for _ in scope)
                            for ref, sha, origin, item in index.execute(
                                f"SELECT * FROM entries WHERE reference IN ({marks})", scope
                            ):
                                copy.write_row((ref, sha, origin, Jsonb(json.loads(item))))
                        conn.execute(MAKE_CANDIDATES)
                        conn.execute(SAVE_SECTIONS)
                        if conn.execute(CHECK_SECTIONS).fetchone()[0]:
                            raise RuntimeError("CPS text or topics missing after import")
                    print(f"Verified {i + len(scope)}/{len(ordered)} references", flush=True)
                if args.retire_legacy:
                    with conn.transaction():
                        conn.execute("LOCK TABLE public.tender_documents_duplicate IN ACCESS EXCLUSIVE MODE")
                        missing = conn.execute("""
                          SELECT count(*) FROM public.tender_documents_duplicate old
                          LEFT JOIN public.tender_documents d ON (d.reference,d.sha256)=(old.reference,old.sha256)
                          WHERE d.legacy_document IS DISTINCT FROM to_jsonb(old)
                        """).fetchone()[0]
                        if missing:
                            raise RuntimeError(f"{missing} old document records are missing")
                        conn.execute("DROP TABLE public.tender_documents_duplicate")
                    print("Legacy document table retired after verification", flush=True)
        finally:
            index.close()


if __name__ == "__main__":
    main()
