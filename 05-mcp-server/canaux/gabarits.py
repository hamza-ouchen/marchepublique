"""
gabarits.py — Registre des gabarits (templates) autorisés pour canaux.

Principe (ADR-001 / brief T2) : AUCUN texte libre n'est jamais envoyé.
Chaque message WhatsApp ou Email envoyé par canaux doit correspondre à
un gabarit de cette liste, avec UNIQUEMENT les variables déclarées ici.

Les 5 noms de gabarits ci-dessous sont les noms OFFICIELS whitelistés
par le brief (`02-brief-ayoub-mcp-canaux.md`, section 3.1) : digest,
conversation, invitation_7j, bienvenue, alerte_hitl. Aucun autre nom
n'est autorisé.

IMPORTANT — statut réel (20/11/2026) :
- "digest" et "alerte_hitl" reprennent les variables déjà définies et
  testées dans la version précédente du squelette (anciennement
  "digest_quotidien" et "alerte_deadline").
- "conversation", "invitation_7j" et "bienvenue" sont des gabarits
  NOUVEAUX, pas encore définis avec l'équipe — les variables
  ci-dessous sont des PLACEHOLDERS À VALIDER, en particulier une fois
  que le vrai template WhatsApp Meta (approuvé/en cours d'examen) est
  disponible : ses variables positionnelles ({{1}}, {{2}}...) doivent
  être recopiées ici dans le même ordre.
- Les gabarits WhatsApp doivent être des templates APPROUVÉS sur Meta
  Business Manager (WhatsApp ne permet pas l'envoi de texte libre en
  dehors d'une conversation déjà ouverte par le client).

Chaque gabarit déclare :
- appelants    : quels agents ont le droit d'utiliser ce gabarit
                 (whitelist — tout autre appelant = acces_refuse)
- canaux       : sur quel(s) canal/canaux ce gabarit peut être envoyé
                 ("whatsapp", "email", ou les deux — ex. le digest
                 part en WhatsApp principal + email de secours)
- variables    : liste des noms de variables autorisées dans ce gabarit
- description  : à quoi sert ce gabarit (pour audit humain)
"""

from dataclasses import dataclass
from typing import Literal

Appelant = Literal["CONCIERGE", "COMPAGNON"]
Canal = Literal["whatsapp", "email"]


@dataclass(frozen=True)
class Gabarit:
    nom: str
    appelants: tuple[Appelant, ...]
    canaux: tuple[Canal, ...]
    variables: tuple[str, ...]
    description: str


# --- Registre des gabarits autorisés (whitelist officielle, brief §3.1) ----

GABARITS: dict[str, Gabarit] = {
    "digest": Gabarit(
        nom="digest",
        appelants=("COMPAGNON",),
        canaux=("whatsapp", "email"),
        variables=("nom_client", "nb_appels_offres", "lien_dashboard"),
        description="Résumé quotidien des appels d'offres pertinents pour un client (distribué par COMPAGNON, WhatsApp principal + email de secours).",
    ),
    "conversation": Gabarit(
        nom="conversation",
        appelants=("CONCIERGE",),
        canaux=("whatsapp",),
        # TODO(Ayoub) : placeholder — a remplacer par les variables
        # positionnelles du template Meta reel une fois approuve.
        variables=("variable_1", "variable_2", "variable_3"),
        description="Réponse conversationnelle de CONCIERGE (FAQ/dossier) — PLACEHOLDER, à aligner sur le template Meta approuvé.",
    ),
    "invitation_7j": Gabarit(
        nom="invitation_7j",
        appelants=("CONCIERGE",),
        canaux=("whatsapp", "email"),
        # TODO(Ayoub) : placeholder — gabarit pas encore défini avec l'équipe.
        variables=("nom_client", "lien_activation", "date_expiration"),
        description="Invitation (valable 7 jours) envoyée après approbation HITL 1 — PLACEHOLDER.",
    ),
    "bienvenue": Gabarit(
        nom="bienvenue",
        appelants=("CONCIERGE",),
        canaux=("whatsapp", "email"),
        # TODO(Ayoub) : placeholder — gabarit pas encore défini avec l'équipe.
        variables=("nom_client", "lien_dashboard"),
        description="Message de bienvenue envoyé après activation du compte — PLACEHOLDER.",
    ),
    "alerte_hitl": Gabarit(
        nom="alerte_hitl",
        appelants=("CONCIERGE",),
        canaux=("whatsapp",),
        variables=("nom_client", "titre_appel_offre", "date_limite"),
        description="Alerte : un dossier À ÉTUDIER nécessite une vérification humaine (HITL 2).",
    ),
}


def obtenir_gabarit(nom: str) -> Gabarit | None:
    """Retourne le gabarit par son nom, ou None s'il n'existe pas (= rejeté)."""
    return GABARITS.get(nom)


def variables_autorisees(nom_gabarit: str) -> tuple[str, ...]:
    """Retourne les variables autorisées pour un gabarit donné."""
    gabarit = obtenir_gabarit(nom_gabarit)
    return gabarit.variables if gabarit else ()
