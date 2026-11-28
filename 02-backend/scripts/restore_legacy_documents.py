"""Verify or restore a local backup of the three legacy document tables."""

import argparse
import csv
import gzip
import hashlib
import json
import os
import re
from pathlib import Path

from dotenv import load_dotenv
import psycopg
from psycopg import sql


TABLES = ("tender_documents_duplicate", "cps_sections2", "cps_sections_3")


def read_manifest(folder: Path) -> dict:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if set(manifest) != set(TABLES):
        raise ValueError("Backup does not contain the three expected tables")
    csv.field_size_limit(100_000_000)
    for table in TABLES:
        item = manifest[table]
        path = folder / f"{table}.csv.gz"
        with path.open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != item["sha256"]:
                raise ValueError(f"Checksum mismatch for {table}")
        with gzip.open(path, "rt", encoding="utf-8", newline="") as stream:
            rows = csv.reader(stream)
            if next(rows) != item["columns"] or sum(1 for _ in rows) != item["rows"]:
                raise ValueError(f"Row count or columns mismatch for {table}")
    return manifest


def restore(folder: Path, manifest: dict, selected: tuple[str, ...] = TABLES) -> None:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    with psycopg.connect(os.environ["DATABASE_URL"]) as conn:
        conn.execute("SET LOCAL lock_timeout = '8s'")
        conn.execute("SET LOCAL maintenance_work_mem = '16MB'")
        for table in selected:
            if conn.execute("SELECT to_regclass(%s)", (f"public.{table}",)).fetchone()[0]:
                raise RuntimeError(f"Refusing to overwrite public.{table}")
        ddl = (folder / "schema.sql").read_text(encoding="utf-8")
        if selected != TABLES:
            names = "|".join(re.escape(table) for table in selected)
            target = re.compile(
                r'(?:CREATE TABLE|ALTER TABLE|ON)\s+"?public"?\."?(?:'
                + names + r')"?(?=\s|\()'
            )
            ddl = "\n".join(line for line in ddl.splitlines()
                            if not line.startswith("--") and target.search(line))
            if not ddl:
                raise ValueError("Selected tables have no matching schema definitions")
        conn.execute(ddl)
        for table in selected:
            qualified = sql.Identifier("public", table)
            columns = sql.SQL(",").join(map(sql.Identifier, manifest[table]["columns"]))
            with gzip.open(folder / f"{table}.csv.gz", "rb") as stream:
                statement = sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT CSV, HEADER)").format(
                    qualified, columns
                )
                with conn.cursor().copy(statement) as destination:
                    while block := stream.read(64 * 1024):
                        destination.write(block)
            restored = conn.execute(sql.SQL("SELECT count(*) FROM {}").format(qualified)).fetchone()[0]
            if restored != manifest[table]["rows"]:
                raise RuntimeError(f"Restore count mismatch for {table}")
        if "tender_documents_duplicate" not in selected:
            return
        sequence = conn.execute("""
            SELECT pg_get_serial_sequence('public.tender_documents_duplicate','id')
        """).fetchone()[0]
        if sequence:
            conn.execute("""
                SELECT setval(%s::regclass, coalesce(max(id), 1), max(id) IS NOT NULL)
                FROM public.tender_documents_duplicate
            """, (sequence,))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("backup", type=Path)
    parser.add_argument("--restore", action="store_true")
    parser.add_argument("--table", choices=TABLES, action="append",
                        help="Restore only the selected legacy table. Repeat to choose several.")
    args = parser.parse_args()
    manifest = read_manifest(args.backup)
    print("Verified:", {table: item["rows"] for table, item in manifest.items()}, flush=True)
    if args.restore:
        selected = tuple(table for table in TABLES if not args.table or table in args.table)
        restore(args.backup, manifest, selected)
        print("Restored:", ", ".join(selected))


if __name__ == "__main__":
    main()
