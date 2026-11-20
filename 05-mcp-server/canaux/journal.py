"""
journal.py — Traçabilité des envois (qui, quoi, quand, résultat).

Norme N8 (voir README du projet) : chaque tentative d'envoi via canaux
doit être journalisée, succès comme échec, pour audit humain ultérieur.
"""

import json
import logging
import os
import time

logging.basicConfig(
    level=os.getenv("JOURNAL_NIVEAU", "INFO"),
    format="%(asctime)s [%(levelname)s] %(message)s",
)
_logger = logging.getLogger("canaux")


def journaliser_tentative(
    outil: str,
    destinataire: str,
    nom_gabarit: str,
    ref: str,
    statut: str,
    details: str = "",
) -> None:
    """Enregistre une tentative d'envoi (quel que soit le résultat).

    - outil       : "envoyer_whatsapp" | "envoyer_email" | "verifier_templates"
    - statut      : "succes" | "rejet_securite" | "echec_api"
    - details     : message d'erreur ou id de message retourné par l'API
    """
    entree = {
        "horodatage": time.time(),
        "outil": outil,
        "destinataire": destinataire,
        "gabarit": nom_gabarit,
        "ref": ref,
        "statut": statut,
        "details": details,
    }

    if statut == "succes":
        _logger.info(json.dumps(entree, ensure_ascii=False))
    else:
        _logger.warning(json.dumps(entree, ensure_ascii=False))
