# =====================================================================
# SOU9NA — chargement partagé de la configuration A2A
# Un seul endroit pour charger .env avant d'importer les modules métier.
# `setdefault` : l'environnement réel garde toujours la priorité.
# =====================================================================
from __future__ import annotations

import os
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DEFAULTS = (
    _ROOT / "02-backend" / ".env",
    _ROOT / "04-langgraph" / "regisseur" / ".env",
)


def charger_env(*chemins: str | Path) -> None:
    """Charge les fichiers .env fournis (ou les deux par défaut)."""
    for chemin in (chemins or _DEFAULTS):
        chemin = Path(chemin)
        if not chemin.is_absolute():
            chemin = _ROOT / chemin
        if not chemin.is_file():
            continue
        for ligne in chemin.read_text(encoding="utf-8-sig").splitlines():
            ligne = ligne.strip()
            if not ligne or ligne.startswith("#") or "=" not in ligne:
                continue
            cle, valeur = ligne.split("=", 1)
            os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))
