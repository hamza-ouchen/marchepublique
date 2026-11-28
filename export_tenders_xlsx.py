"""Export the tenders table to a formatted Excel workbook.

Usage:
    py -B export_tenders_xlsx.py [output.xlsx] [limit]

Reads DATABASE_URL through the project's normal environment loader, so no
credential is written into this file.
"""
from __future__ import annotations

import os
import sys
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

import xlsxwriter

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "04-langgraph"))

from a2a_env import charger_env  # noqa: E402

charger_env()

import psycopg  # noqa: E402
from psycopg.rows import dict_row  # noqa: E402

OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "tenders-all.xlsx"
LIMIT = int(sys.argv[2]) if len(sys.argv) > 2 else None
REFS_FILE = Path(sys.argv[3]) if len(sys.argv) > 3 else None

COLUMNS = [
    ("reference", "Référence", 26),
    ("reference_officielle", "Référence officielle", 26),
    ("organisme", "Organisme", 42),
    ("objet", "Objet", 80),
    ("secteur", "Secteur", 22),
    ("region", "Région", 28),
    ("montant_mad", "Montant (MAD)", 16),
    ("caution_mad", "Caution (MAD)", 16),
    ("delai_jours", "Délai (jours)", 12),
    ("lots", "Lots", 40),
    ("qualifications_exigees", "Qualifications exigées", 50),
    ("date_publication", "Publication", 14),
    ("heure_publication", "Heure publication", 13),
    ("date_remise", "Date remise", 14),
    ("heure_remise", "Heure remise", 13),
    ("date_collecte", "Date collecte", 14),
    ("statut", "Statut", 12),
    ("source", "Source", 14),
    ("offer_type", "Type", 18),
    ("source_url", "URL source", 70),
    ("cree_le", "Créé le", 20),
    ("mis_a_jour_le", "Mis à jour le", 20),
    ("enriched_at", "Enrichi le", 20),
]

SQL = """
SELECT reference, reference_officielle, organisme, objet, secteur, region,
       montant_mad, caution_mad, delai_jours, lots, qualifications_exigees,
       date_publication, heure_publication, date_remise, heure_remise,
       date_collecte, statut, source, offer_type, source_url, cree_le,
       mis_a_jour_le, enriched_at
FROM tenders
ORDER BY date_remise NULLS LAST, reference
"""

REFS = None
if REFS_FILE:
    REFS = [line.strip() for line in REFS_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip()]

with psycopg.connect(os.environ["DATABASE_URL"], row_factory=dict_row) as conn:
    if REFS:
        rows = conn.execute(
            SQL.replace("ORDER BY date_remise NULLS LAST, reference",
                        "WHERE reference = ANY(%s) ORDER BY array_position(%s::text[], reference)"),
            (REFS, REFS),
        ).fetchall()
    elif LIMIT:
        rows = conn.execute(SQL + " LIMIT %s", (LIMIT,)).fetchall()
    else:
        rows = conn.execute(SQL).fetchall()

OUT.parent.mkdir(parents=True, exist_ok=True)
wb = xlsxwriter.Workbook(str(OUT), {"constant_memory": True})
ws = wb.add_worksheet("Tenders")

header_fmt = wb.add_format({
    "bold": True, "font_color": "#FFFFFF", "bg_color": "#1F4E78",
    "border": 1, "align": "center", "valign": "vcenter",
})
text_fmt = wb.add_format({"valign": "top"})
wrap_fmt = wb.add_format({"valign": "top", "text_wrap": True})
date_fmt = wb.add_format({"num_format": "yyyy-mm-dd", "valign": "top"})
datetime_fmt = wb.add_format({"num_format": "yyyy-mm-dd hh:mm", "valign": "top"})
money_fmt = wb.add_format({"num_format": "#,##0.00", "valign": "top"})
int_fmt = wb.add_format({"num_format": "0", "valign": "top"})

for col_idx, (_, title, width) in enumerate(COLUMNS):
    ws.write(0, col_idx, title, header_fmt)
    ws.set_column(col_idx, col_idx, width)

WRAP_COLUMNS = {"organisme", "objet", "lots", "qualifications_exigees", "source_url"}
DATE_COLUMNS = {"date_publication", "date_remise", "date_collecte"}
DATETIME_COLUMNS = {"cree_le", "mis_a_jour_le", "enriched_at"}
MONEY_COLUMNS = {"montant_mad", "caution_mad"}


def write_value(row_idx: int, col_idx: int, key: str, value) -> None:
    if value is None:
        return
    if isinstance(value, (list, tuple)):
        value = ", ".join(str(item) for item in value)
    if key in DATE_COLUMNS and isinstance(value, date):
        ws.write_datetime(row_idx, col_idx, value, date_fmt)
    elif key in DATETIME_COLUMNS and isinstance(value, datetime):
        ws.write_datetime(row_idx, col_idx, value.replace(tzinfo=None), datetime_fmt)
    elif key in MONEY_COLUMNS and isinstance(value, Decimal):
        ws.write_number(row_idx, col_idx, float(value), money_fmt)
    elif key == "delai_jours":
        ws.write_number(row_idx, col_idx, int(value), int_fmt)
    elif isinstance(value, (int, float, Decimal)):
        ws.write_number(row_idx, col_idx, float(value), text_fmt)
    else:
        ws.write_string(
            row_idx, col_idx, str(value),
            wrap_fmt if key in WRAP_COLUMNS else text_fmt,
        )


for row_idx, row in enumerate(rows, start=1):
    for col_idx, (key, _, _) in enumerate(COLUMNS):
        write_value(row_idx, col_idx, key, row.get(key))

ws.freeze_panes(1, 0)
ws.autofilter(0, 0, max(len(rows), 1), len(COLUMNS) - 1)
wb.close()
print(f"Wrote {len(rows)} tenders to {OUT}")
