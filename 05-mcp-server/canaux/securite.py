"""
securite.py — Les 4 contrôles de sécurité que CHAQUE envoi doit passer
avant d'atteindre client_whatsapp.py ou client_email.py.

1. Appelant    : l'agent appelant (CONCIERGE/COMPAGNON) a-t-il le droit
                 d'utiliser ce gabarit précis ? (brief §3.1 — sinon
                 acces_refuse)
2. Whitelist   : le gabarit demandé existe-t-il et les variables
                 fournies sont-elles exactement celles autorisées ?
3. Idempotence : ce `ref` a-t-il déjà été traité ? (évite les doublons
                 en cas de retry réseau côté agent appelant)
4. Rate limit  : le destinataire/la conversation n'a-t-il pas dépassé
                 les seuils définis dans .env ?

Toute violation lève une SecuriteError — serveur.py doit l'attraper et
renvoyer un refus clair, JAMAIS envoyer le message.
"""

import os
import re
import time
from dataclasses import dataclass, field

from gabarits import obtenir_gabarit


class SecuriteError(Exception):
    """Levée quand un envoi ne respecte pas une règle de sécurité."""


# --- 0. Format du destinataire ------------------------------------------
# Brief : un numéro WhatsApp doit être au format E.164 (ex. "212612345678")
# — "+" optionnel, PAS de 0 initial après l'indicatif pays, 8 à 15 chiffres
# au total (norme E.164 : max 15 chiffres, hors le "+").
# Un email doit avoir une forme minimale valide (on ne vérifie pas la
# délivrabilité ici, juste la forme — Brevo/le fournisseur fera le reste).

_REGEX_E164 = re.compile(r"^\+?[1-9]\d{7,14}$")
_REGEX_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def verifier_destinataire(canal: str, destinataire: str) -> None:
    """Vérifie que `destinataire` a un format valide pour ce canal.

    - canal="whatsapp" : format E.164 (ex. "212612345678").
    - canal="email"    : forme email basique (local@domaine.tld).
    """
    if canal == "whatsapp":
        if not _REGEX_E164.match(destinataire):
            raise SecuriteError(
                f"Numéro WhatsApp invalide (format E.164 attendu, ex. "
                f"'212612345678') : '{destinataire}'"
            )
    elif canal == "email":
        if not _REGEX_EMAIL.match(destinataire):
            raise SecuriteError(f"Adresse email invalide : '{destinataire}'")
    else:
        raise SecuriteError(f"Canal inconnu : '{canal}'")


# --- 1. Appelant --------------------------------------------------------

def verifier_appelant(nom_gabarit: str, appelant: str) -> None:
    """Vérifie que l'agent appelant a le droit d'utiliser ce gabarit.

    Brief §3.1 : appelant hors whitelist du gabarit -> acces_refuse.
    Fait exprès AVANT verifier_gabarit pour ne même pas révéler si le
    gabarit existe à un appelant non autorisé à le voir.
    """
    gabarit = obtenir_gabarit(nom_gabarit)
    if gabarit is None:
        raise SecuriteError(f"Gabarit inconnu/non autorisé : '{nom_gabarit}'")

    if appelant not in gabarit.appelants:
        raise SecuriteError(
            f"acces_refuse : '{appelant}' n'est pas autorisé à utiliser "
            f"le gabarit '{nom_gabarit}' (autorisé à : {gabarit.appelants})"
        )


# --- 2. Whitelist --------------------------------------------------------

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


# --- 3. Idempotence --------------------------------------------------------
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


# --- 4. Rate limiting --------------------------------------------------------
# NOTE : stockage en mémoire pour ce squelette, même remarque que ci-dessus.

@dataclass
class _CompteurDestinataire:
    horodatages: list[float] = field(default_factory=list)


_COMPTEURS: dict[str, _CompteurDestinataire] = {}


def _seuil(nom_var: str, defaut: int) -> int:
    return int(os.getenv(nom_var, defaut))


def verifier_rate_limit(destinataire: str) -> None:
    """Vérifie les 3 seuils définis dans .env pour ce destinataire.

    Lève SecuriteError si l'un des seuils est dépassé.
    """
    maintenant = time.time()
    compteur = _COMPTEURS.setdefault(destinataire, _CompteurDestinataire())

    burst_max = _seuil("RATE_LIMIT_BURST_MAX", 10)
    fenetre_conversation = _seuil("RATE_LIMIT_PAR_CONVERSATION_5MIN", 1) and 5 * 60
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
    if len(appels_conversation) >= 1:
        raise SecuriteError(
            f"Trop tôt pour reparler à '{destinataire}' "
            f"(limite 1 message / {fenetre_conversation // 60} min)"
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
    appelant: str,
    nom_gabarit: str,
    variables_fournies: dict[str, str],
    destinataire: str,
    ref: str,
    canal: str,
) -> None:
    """Fait passer un envoi par les 5 contrôles, dans cet ordre.

    N'importe quelle étape peut lever SecuriteError — l'appelant
    (serveur.py) doit alors refuser l'envoi, sans jamais appeler
    client_whatsapp.py ou client_email.py.
    """
    verifier_destinataire(canal, destinataire)
    verifier_appelant(nom_gabarit, appelant)
    verifier_gabarit(nom_gabarit, variables_fournies)
    verifier_idempotence(ref)
    verifier_rate_limit(destinataire)


def marquer_succes(destinataire: str, ref: str) -> None:
    """À appeler par serveur.py UNIQUEMENT après un envoi réussi."""
    marquer_ref_traite(ref)
    marquer_envoi(destinataire)
