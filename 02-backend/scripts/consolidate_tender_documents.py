"""Resume the document and CPS consolidation in bounded transactions."""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg


BACKEND = Path(__file__).resolve().parents[1]
MIGRATION = BACKEND / "migrations" / "022_consolidate_tender_documents.sql"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=150)
    parser.add_argument("--resume-offset", type=int, default=0,
                        help="Resume after an already committed range of ordered references.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--finalize", action="store_true",
                      help="After copying, verify every source record and retire the legacy tables.")
    mode.add_argument("--finalize-only", action="store_true",
                      help="Verify and retire legacy tables after all batches were already copied.")
    options = parser.parse_args()
    if options.batch_size < 1 or options.resume_offset < 0:
        parser.error("batch size must be positive and resume offset non-negative")
    load_dotenv(BACKEND / ".env")
    setup, body = MIGRATION.read_text(encoding="utf-8").split("-- MERGE BATCH")
    batch, final = body.split("-- MERGE FINAL")
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True,
                         keepalives=1, keepalives_idle=20) as conn:
        if not conn.execute("SELECT to_regclass('public.tender_documents_duplicate')").fetchone()[0]:
            print("Legacy tables already retired.")
            return
        conn.execute("SET lock_timeout = '8s'")
        conn.execute("SET statement_timeout = '150s'")
        if options.finalize_only:
            with conn.transaction():
                conn.execute(final)
            print("Verified original rows and retired the legacy tables.", flush=True)
            return
        with conn.transaction():
            conn.execute(setup)
        references = [row[0] for row in conn.execute("""
            SELECT reference FROM public.tender_documents_duplicate
            UNION SELECT d.reference
            FROM public.cps_sections2 s JOIN public.tender_documents d ON d.id=s.document_id
            ORDER BY reference
        """)]
        for offset in range(options.resume_offset, len(references), options.batch_size):
            scope = references[offset:offset + options.batch_size]
            with conn.transaction():
                conn.execute("CREATE TEMP TABLE merge_scope (reference text PRIMARY KEY) ON COMMIT DROP")
                conn.execute("INSERT INTO merge_scope SELECT unnest(%s::text[])", (scope,))
                conn.execute("ANALYZE merge_scope")
                conn.execute(batch)
            print(f"Saved batch through {offset + len(scope)}/{len(references)} references", flush=True)
        if options.finalize:
            with conn.transaction():
                conn.execute(final)
            print("Verified original rows and retired the legacy tables.", flush=True)


if __name__ == "__main__":
    main()
