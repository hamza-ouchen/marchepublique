"""Merge exact duplicate CPS sections without losing source metadata."""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv
import psycopg


MERGE = """
WITH duplicates AS MATERIALIZED (
    SELECT array_agg(s.id ORDER BY s.section_no,s.id) AS ids
    FROM public.cps_sections s
    WHERE s.document_id=ANY(%s)
    GROUP BY s.document_id,s.texte,s.numero,s.titre,s.pages_section
    HAVING count(*)>1
), members AS MATERIALIZED (
    SELECT d.ids[1] AS keeper, s.*
    FROM duplicates d JOIN public.cps_sections s ON s.id=ANY(d.ids)
), tags AS (
    SELECT m.keeper,array_agg(DISTINCT tag ORDER BY tag) AS sujets
    FROM members m CROSS JOIN LATERAL unnest(m.sujets) tag
    GROUP BY m.keeper
), provenance AS (
    SELECT keeper,jsonb_agg(DISTINCT item) AS history
    FROM (
        SELECT m.keeper,p.item FROM members m
        CROSS JOIN LATERAL jsonb_array_elements(m.legacy_sections) p(item)
        UNION ALL
        SELECT m.keeper,jsonb_build_object('origin','cps_sections',
            'row',to_jsonb(m)-'keeper'-'texte'-'legacy_sections')
        FROM members m WHERE m.id<>m.keeper
    ) records GROUP BY keeper
), saved AS (
    UPDATE public.cps_sections s
    SET sujets=coalesce(tags.sujets,'{}'),legacy_sections=p.history
    FROM provenance p LEFT JOIN tags USING(keeper)
    WHERE s.id=p.keeper RETURNING s.id
)
DELETE FROM public.cps_sections s USING members m,saved
WHERE s.id=m.id AND m.id<>m.keeper AND saved.id=m.keeper
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--same-text", action="store_true",
                        help="Also consolidate repeat text at different pages or headings; retain the other metadata.")
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    with psycopg.connect(os.environ["DATABASE_URL"], autocommit=True,
                         connect_timeout=8) as conn:
        if conn.execute("SHOW transaction_read_only").fetchone()[0] != "off":
            raise RuntimeError("PostgreSQL is read-only")
        conn.execute("SET lock_timeout='5s'")
        conn.execute("SET statement_timeout='60s'")
        scope_sql = """
            SELECT DISTINCT document_id FROM (
                SELECT document_id,sha256(convert_to(texte,'UTF8')),numero,titre,pages_section
                FROM public.cps_sections GROUP BY 1,2,3,4,5 HAVING count(*)>1
            ) repeated ORDER BY document_id
        """
        merge_sql = MERGE
        if args.same_text:
            scope_sql = scope_sql.replace(",numero,titre,pages_section", "").replace("1,2,3,4,5", "1,2")
            merge_sql = merge_sql.replace(",s.numero,s.titre,s.pages_section", "")
        docs = [row[0] for row in conn.execute(scope_sql)]
        removed = 0
        for offset in range(0, len(docs), args.batch_size):
            group = docs[offset:offset + args.batch_size]
            with conn.transaction():
                count = conn.execute(merge_sql, (group,)).rowcount
            removed += count
            print(f"{offset + len(group)}/{len(docs)} documents; {removed} duplicates merged", flush=True)
        print(f"Exact duplicate sections removed: {removed}", flush=True)


if __name__ == "__main__":
    main()
