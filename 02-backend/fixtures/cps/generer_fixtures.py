#!/usr/bin/env python3
"""Génère les PDF de fixtures CPS — AUCUNE dépendance externe.

Usage :
    py generer_fixtures.py

Entrées : sources/*.txt   (titres numérotés « 1. » / « 2.1 »)
Sorties : pdfs/<année>/<référence>/<document>.pdf
          attendu/*.json  (sections attendues, pour les futurs tests)

Les documents sont SYNTHÉTIQUES : aucune donnée réelle du portail,
aucun PDF réel, aucun secret. Ils servent à tester le découpage et les
statuts de `cps_uploads` (migration 005_cps.sql).
"""

from __future__ import annotations

import json
import re
import sys
import textwrap
from pathlib import Path

RACINE = Path(__file__).resolve().parent
SOURCES = RACINE / "sources"
PDFS = RACINE / "pdfs"
ATTENDU = RACINE / "attendu"

MOTIF_TITRE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s+(.{2,100})$")
LARGEUR_LIGNE = 96
LIGNES_PAR_PAGE = 44

# ── Catalogue des fixtures ────────────────────────────────────────────
DOCUMENTS = [
    {
        "source": "2026-DTR-0123-cps.txt",
        "reference": "2026/DTR/0123",
        "document_name": "cps.pdf",
        "storage_path": "2026/2026-DTR-0123/cps.pdf",
        "pdf": "2026-DTR-0123/cps.pdf",
        "attendu": "a1-0123-cps.json",
        "couche_texte": True,
        "extraction": "texte",
        "cas": "A1 — CPS simple (cas nominal)",
    },
    {
        "source": "2026-DTR-0124-cps.txt",
        "reference": "2026/DTR/0124",
        "document_name": "cps.pdf",
        "storage_path": "2026/2026-DTR-0124/cps.pdf",
        "pdf": "2026-DTR-0124/cps.pdf",
        "attendu": "a2-0124-cps.json",
        "couche_texte": True,
        "extraction": "texte",
        "cas": "A2 — CPS + addenda (multi-documents)",
    },
    {
        "source": "2026-DTR-0124-addenda-1.txt",
        "reference": "2026/DTR/0124",
        "document_name": "addenda-1.pdf",
        "storage_path": "2026/2026-DTR-0124/addenda-1.pdf",
        "pdf": "2026-DTR-0124/addenda-1.pdf",
        "attendu": "a2-0124-addenda-1.json",
        "couche_texte": True,
        "extraction": "texte",
        "cas": "A2 — addenda n° 1 (second document du même AO)",
    },
    {
        "source": "2026-DTR-0131-cps.txt",
        "reference": "2026/DTR/0131",
        "document_name": "cps.pdf",
        "storage_path": "2026/2026-DTR-0131/cps.pdf",
        "pdf": "2026-DTR-0131/cps.pdf",
        "attendu": "a3-0131-cps.json",
        "couche_texte": False,
        "extraction": "ocr_requis",
        "cas": "A3 — PDF sans couche texte (branche OCR)",
    },
]


# ── Découpage déterministe (même convention que le futur Midouni) ────
def decouper(texte: str) -> tuple[list[str], list[dict]]:
    """Retourne (en-tête, sections) ; heading = ligne « 1. » ou « 2.1 ».

    Une rubrique sans texte propre (titre de chapitre qui ne contient que
    des sous-rubriques) n'est PAS une section citable : elle est ignorée.
    """
    entete: list[str] = []
    sections: list[dict] = []
    courante: dict | None = None

    for brute in texte.splitlines():
        ligne = brute.strip()
        if not ligne:
            continue
        trouve = MOTIF_TITRE.match(ligne)
        # Un titre commence par une majuscule : « 15 jours ... » reste du texte.
        if trouve and trouve.group(2)[:1].isupper():
            courante = {
                "numero": trouve.group(1),
                "titre": trouve.group(2).strip(),
                "paragraphes": [],
            }
            sections.append(courante)
        elif courante is None:
            entete.append(ligne)
        else:
            courante["paragraphes"].append(ligne)

    # Document sans aucun titre numéroté : une seule section « Document ».
    if not sections:
        sections = [{"numero": None, "titre": "Document", "paragraphes": entete}]
        entete = []

    resultat = []
    for section in sections:
        corps = "\n".join(section["paragraphes"]).strip()
        if not corps:                                   # rubrique conteneur : pas citable
            continue
        resultat.append({
            "section_no": len(resultat) + 1,
            "numero": section["numero"],
            "titre": section["titre"],
            "debut": corps[:80],
            "longueur": len(corps),
        })
    return entete, resultat


# ── Générateur PDF minimal (PDF 1.4, Helvetica, WinAnsi) ─────────────
def _echapper(texte: str) -> bytes:
    sortie = bytearray()
    for octet in texte.encode("cp1252", errors="replace"):
        if octet in (0x28, 0x29, 0x5C):                 # ( ) \
            sortie += b"\\" + bytes([octet])
        elif 32 <= octet < 127:
            sortie.append(octet)
        else:
            sortie += ("\\%03o" % octet).encode("ascii")
    return bytes(sortie)


def _flux(lignes: list[str]) -> bytes:
    if not lignes:                                      # page « scannée » sans texte
        return b"1 w 20 20 555 802 re S\n"
    morceaux = [b"BT /F1 10 Tf 14 TL 50 792 Td\n"]
    for ligne in lignes:
        morceaux.append(b"(" + _echapper(ligne) + b") Tj T*\n")
    morceaux.append(b"ET\n")
    return b"".join(morceaux)


def _pages(texte: str) -> list[list[str]]:
    lignes: list[str] = []
    for brute in texte.splitlines():
        ligne = brute.strip()
        if not ligne:
            continue
        lignes.extend(textwrap.wrap(ligne, width=LARGEUR_LIGNE) or [""])
        lignes.append("")
    while lignes and lignes[-1] == "":
        lignes.pop()
    return [lignes[i:i + LIGNES_PAR_PAGE] for i in range(0, len(lignes), LIGNES_PAR_PAGE)] or [[]]


def ecrire_pdf(chemin: Path, pages: list[list[str]]) -> None:
    objets: dict[int, bytes] = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        3: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    }
    kids: list[int] = []
    numero = 4
    for lignes in pages:
        id_page, id_contenu = numero, numero + 1
        numero += 2
        kids.append(id_page)
        flux = _flux(lignes)
        objets[id_contenu] = (
            b"<< /Length " + str(len(flux)).encode("ascii") + b" >>\nstream\n"
            + flux + b"\nendstream"
        )
        objets[id_page] = (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] "
            b"/Resources << /Font << /F1 3 0 R >> >> /Contents "
            + str(id_contenu).encode("ascii") + b" 0 R >>"
        )

    objets[2] = (
        b"<< /Type /Pages /Kids ["
        + b" ".join(str(k).encode("ascii") + b" 0 R" for k in kids)
        + b"] /Count " + str(len(kids)).encode("ascii") + b" >>"
    )

    sortie = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets: dict[int, int] = {}
    for identifiant in sorted(objets):
        offsets[identifiant] = len(sortie)
        sortie += str(identifiant).encode("ascii") + b" 0 obj\n" + objets[identifiant] + b"\nendobj\n"

    maxi = max(objets)
    position_xref = len(sortie)
    sortie += b"xref\n0 " + str(maxi + 1).encode("ascii") + b"\n0000000000 65535 f \n"
    for identifiant in range(1, maxi + 1):
        sortie += ("%010d 00000 n \n" % offsets[identifiant]).encode("ascii")
    sortie += (
        b"trailer\n<< /Size " + str(maxi + 1).encode("ascii") + b" /Root 1 0 R >>\n"
        b"startxref\n" + str(position_xref).encode("ascii") + b"\n%%EOF\n"
    )

    chemin.parent.mkdir(parents=True, exist_ok=True)
    chemin.write_bytes(bytes(sortie))


# ── Programme ────────────────────────────────────────────────────────
def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ATTENDU.mkdir(parents=True, exist_ok=True)

    for document in DOCUMENTS:
        texte = (SOURCES / document["source"]).read_text(encoding="utf-8-sig")
        _, sections = decouper(texte)
        if document["extraction"] == "ocr_requis":
            sections = []

        pages = _pages(texte) if document["couche_texte"] else [[]]
        chemin_pdf = PDFS / document["pdf"]
        ecrire_pdf(chemin_pdf, pages)

        attendu = {
            "cas": document["cas"],
            "reference": document["reference"],
            "document_name": document["document_name"],
            "storage_path": document["storage_path"],
            "pdf": document["pdf"],
            "extraction": document["extraction"],
            "source_verite_terrain": f"sources/{document['source']}",
            "sections": sections,
        }
        (ATTENDU / document["attendu"]).write_text(
            json.dumps(attendu, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(f"OK  {document['pdf']}  ({len(pages)} page(s), {len(sections)} section(s)) "
              f"— {document['cas']}")

    print(f"\n{len(DOCUMENTS)} document(s) généré(s) dans {PDFS} et {ATTENDU}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
