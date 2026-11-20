"""
securite.py — Les 3 contrôles de sécurité que CHAQUE envoi doit passer
avant d'atteindre client_whatsapp.py ou client_brevo.py.

1. Whitelist   : le gabarit demandé existe-t-il et les variables
                 fournies sont-elles exactement celles autorisées ?
2. Idempotence : ce `ref` a-t-il déjà été traité ? (évite les doublons
                 en cas de retry réseau côté agent appelant)
3. Rate limit  : le destinataire/la conversation n'a-t-il pas dépassé
                 les seuils définis dans .env ?

Toute violation lève une SecuriteError — serveur.py doit l'attraper et
renvoyer un refus clair, JAMAIS envoyer le message.
"""

import os
import time
from dataclasses import dataclass, field

from gabarits import obtenir_gabarit


class SecuriteError(Exception):
    """Levée quand un envoi ne respecte pas une règle de sécurité."""


# --- 1. Whitelist --------------------------------------------------------

def verifier_gabarit(nom_gabarit: str, variables_fournies: dict[str, str]) -> None:
    """Vérifie que le gabarit existe et que les variables fournies
    correspondent EXACTEMENT à celles autorisées (ni plus, ni moins)."""
    gabarit = obtenir_gabarit(nom_gabarit)
    if gabarit is None:
        raise SecuriteError(f"Gabarit inconnu/non autorisé : '{nom_gabarit}'")

    attendues = set(gabarit.variables)
    fournies = set(variables_fournies.keys())

    if fournies != attendues:
        manquantes = attendues - fournies
        en_trop = fournies - attendues
        details = []
        if manquantes:
            details.append(f"manquantes={manquantes}")
        if en_trop:
            details.append(f"non autorisées={en_trop}")
        raise SecuriteError(
            f"Variables invalides pour '{nom_gabarit}' : {', '.join(details)}"
        )


# --- 2. Idempotence --------------------------------------------------------
# NOTE : stockage en mémoire pour ce squelette (simple dict + horodatage).
# TODO(Ayoub) : remplacer par un stockage persistant (fichier ou base
# légère) si le serveur doit survivre à un redémarrage sans perdre
# l'historique des `ref` déjà traités.

_REFS_TRAITES: dict[str, float] = {}
_DUREE_RETENTION_REF_SECONDES = 24 * 60 * 60  # 24h


def verifier_idempotence(ref: str) -> None:
    """Lève une erreur si ce `ref` a déjà été traité récemment."""
    maintenant = time.time()
    _purger_refs_expires(maintenant)

    if ref in _REFS_TRAITES:
        raise SecuriteError(f"Référence déjà traitée (doublon rejeté) : '{ref}'")


def marquer_ref_traite(ref: str) -> None:
    """À appeler APRÈS un envoi réussi, pour enregistrer le `ref`."""
    _REFS_TRAITES[ref] = time.time()


def _purger_refs_expires(maintenant: float) -> None:
    expires = [
        r for r, t in _REFS_TRAITES.items()
        if maintenant - t > _DUREE_RETENTION_REF_SECONDES
    ]
    for r in expires:
        del _REFS_TRAITES[r]


# --- 3. Rate limiting --------------------------------------------------------
# NOTE : stockage en mémoire pour ce squelette, même remarque que ci-dessus.

@dataclass
class _CompteurDestinataire:
    horodatages: list[float] = field(default_factory=list)


_COMPTEURS: dict[str, _CompteurDestinataire] = {}


def _seuil(nom_var: str, defaut: int) -> int:
    brut = os.getenv(nom_var, str(defaut))
    # Tolérer les commentaires en fin de ligne : "10   # ex: ..."
    brut = brut.split("#", 1)[0].strip()
    try:
        return int(brut.split()[0]) if brut.split() else defaut
    except (ValueError, IndexError):
        return defaut


def verifier_rate_limit(destinataire: str) -> None:
    """Vérifie les 3 seuils définis dans .env pour ce destinataire.

    Lève SecuriteError si l'un des seuils est dépassé.
    """
    maintenant = time.time()
    compteur = _COMPTEURS.setdefault(destinataire, _CompteurDestinataire())

    burst_max = _seuil("RATE_LIMIT_BURST_MAX", 10)
    limite_conversation = _seuil("RATE_LIMIT_PAR_CONVERSATION_5MIN", 1)
    fenetre_conversation = 5 * 60
    fenetre_24h = 24 * 60 * 60
    max_24h = _seuil("RATE_LIMIT_PAR_DESTINATAIRE_24H", 1)

    # Nettoyage : ne garder que les horodatages des dernières 24h
    compteur.horodatages = [
        h for h in compteur.horodatages if maintenant - h < fenetre_24h
    ]

    # Burst : combien d'appels dans la dernière minute ?
    appels_recents = [h for h in compteur.horodatages if maintenant - h < 60]
    if len(appels_recents) >= burst_max:
        raise SecuriteError(
            f"Burst dépassé pour '{destinataire}' "
            f"({len(appels_recents)}/{burst_max} appels/minute)"
        )

    # Par conversation (fenêtre courte, ex. 5 min)
    appels_conversation = [
        h for h in compteur.horodatages if maintenant - h < fenetre_conversation
    ]
    if len(appels_conversation) >= limite_conversation:
        raise SecuriteError(
            f"Trop tôt pour reparler à '{destinataire}' "
            f"(limite {limite_conversation} message(s) / 5 min)"
        )

    # Par destinataire sur 24h (ex. 1 digest / jour)
    if len(compteur.horodatages) >= max_24h:
        raise SecuriteError(
            f"Limite 24h atteinte pour '{destinataire}' "
            f"({len(compteur.horodatages)}/{max_24h})"
        )


def marquer_envoi(destinataire: str) -> None:
    """À appeler APRÈS un envoi réussi, pour enregistrer l'horodatage."""
    compteur = _COMPTEURS.setdefault(destinataire, _CompteurDestinataire())
    compteur.horodatages.append(time.time())


# --- Point d'entrée unique utilisé par serveur.py --------------------------

def verifier_envoi(
    nom_gabarit: str,
    variables_fournies: dict[str, str],
    destinataire: str,
    ref: str,
) -> None:
    """Fait passer un envoi par les 3 contrôles, dans cet ordre.

    N'importe quelle étape peut lever SecuriteError — l'appelant
    (serveur.py) doit alors refuser l'envoi, sans jamais appeler
    client_whatsapp.py ou client_brevo.py.
    """
    verifier_gabarit(nom_gabarit, variables_fournies)
    verifier_idempotence(ref)
    verifier_rate_limit(destinataire)


def marquer_succes(destinataire: str, ref: str) -> None:
    """À appeler par serveur.py UNIQUEMENT après un envoi réussi."""
    marquer_ref_traite(ref)
    marquer_envoi(destinataire)
