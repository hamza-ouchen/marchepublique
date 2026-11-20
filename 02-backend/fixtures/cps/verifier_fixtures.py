#!/usr/bin/env python3
"""Vérifie la cohérence des fixtures CPS — aucune dépendance externe.

Usage :
    py verifier_fixtures.py

Contrôle : PDF présents et bien formés + JSON « attendu » synchronisé
avec les sources. À lancer après toute modification d'une source.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from generer_fixtures import ATTENDU, DOCUMENTS, PDFS, SOURCES, decouper  # noqa: E402

CHAMPS = ("section_no", "numero", "titre", "debut", "longueur")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    erreurs: list[str] = []

    for document in DOCUMENTS:
        pdf = PDFS / document["pdf"]
        if not pdf.exists():
            erreurs.append(f"{document['pdf']} : PDF absent — lancer generer_fixtures.py")
        else:
            contenu = pdf.read_bytes()
            if not contenu.startswith(b"%PDF-1.4") or not contenu.rstrip().endswith(b"%%EOF"):
                erreurs.append(f"{document['pdf']} : en-tête/pied PDF invalide")
            if len(contenu) < 300:
                erreurs.append(f"{document['pdf']} : fichier trop petit ({len(contenu)} octets)")

        fichier_attendu = ATTENDU / document["attendu"]
        if not fichier_attendu.exists():
            erreurs.append(f"{document['attendu']} : JSON attendu absent")
            continue

        attendu = json.loads(fichier_attendu.read_text(encoding="utf-8"))
        texte = (SOURCES / document["source"]).read_text(encoding="utf-8-sig")
        _, sections = decouper(texte)

        if document["extraction"] == "ocr_requis":
            if attendu["sections"]:
                erreurs.append(f"{document['attendu']} : un PDF sans texte ne doit pas attendre de sections")
        else:
            recalcule = [{champ: section[champ] for champ in CHAMPS} for section in sections]
            if attendu["sections"] != recalcule:
                erreurs.append(f"{document['attendu']} : désynchronisé — relancer generer_fixtures.py")

    if erreurs:
        print("ÉCHEC")
        for erreur in erreurs:
            print(f"  - {erreur}")
        return 1

    print(f"OK — {len(DOCUMENTS)} document(s) : PDF valides et JSON attendus synchronisés")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
