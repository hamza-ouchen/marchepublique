"""
gabarits.py — Registre des gabarits (templates) autorisés pour canaux.

Principe (ADR-001 / brief T2) : AUCUN texte libre n'est jamais envoyé.
Chaque message WhatsApp ou Email envoyé par canaux doit correspondre à
un gabarit de cette liste, avec UNIQUEMENT les variables déclarées ici.

IMPORTANT — à faire avant la mise en production :
Les gabarits WhatsApp doivent être des templates APPROUVÉS sur Meta
Business Manager (WhatsApp ne permet pas l'envoi de texte libre en
dehors d'une conversation déjà ouverte par le client). Les noms et
variables ci-dessous sont des PLACEHOLDERS à remplacer par les vrais
templates une fois créés/validés sur Meta — ne pas les utiliser tels
quels en production.

Chaque gabarit déclare :
- canal       : "whatsapp" ou "email"
- variables   : liste des noms de variables autorisées dans ce gabarit
- description : à quoi sert ce gabarit (pour audit humain)
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True)
class Gabarit:
    nom: str
    canal: Literal["whatsapp", "email"]
    variables: tuple[str, ...]
    description: str
    langue: str = "fr"   # code langue Meta (fr, ar, en, ...)


# --- Registre des gabarits autorisés ---------------------------------
# TODO(Ayoub) : remplacer par les vrais noms de templates Meta une fois
# créés et approuvés dans Meta Business Manager.

GABARITS: dict[str, Gabarit] = {
    "hello_world": Gabarit(
        nom="hello_world",
        canal="whatsapp",
        variables=(),
        description="Template de test Meta (hello_world) — présent par défaut sur tout compte WhatsApp Business.",
        langue="en_US",
    ),
    "digest_quotidien": Gabarit(
        nom="digest_quotidien",
        canal="whatsapp",
        variables=("nom_client", "nb_appels_offres", "lien_dashboard"),
        description="Résumé quotidien des appels d'offres pertinents pour un client.",
        langue="fr",
    ),
    "digest_quotidien_fr": Gabarit(
        nom="digest_quotidien_fr",
        canal="whatsapp",
        variables=("nom_client", "nb_appels_offres", "lien_dashboard"),
        description="Résumé quotidien des appels d'offres pertinents pour un client (FR).",
        langue="fr",
    ),
    "digest_quotidien_ar": Gabarit(
        nom="digest_quotidien_ar",
        canal="whatsapp",
        variables=("nom_client", "nb_appels_offres", "lien_dashboard"),
        description="ملخص يومي لصفقات المناقصات ذات الصلة للعميل (AR).",
        langue="ar",
    ),
    "alerte_deadline": Gabarit(
        nom="alerte_deadline",
        canal="whatsapp",
        variables=("nom_client", "titre_appel_offre", "date_limite"),
        description="Alerte : une échéance de dépôt approche pour un appel d'offres suivi.",
        langue="fr",
    ),
    "alerte_deadline_fr": Gabarit(
        nom="alerte_deadline_fr",
        canal="whatsapp",
        variables=("nom_client", "titre_appel_offre", "date_limite"),
        description="Alerte : une échéance de dépôt approche (FR).",
        langue="fr",
    ),
    "alerte_deadline_ar": Gabarit(
        nom="alerte_deadline_ar",
        canal="whatsapp",
        variables=("nom_client", "titre_appel_offre", "date_limite"),
        description="تنبيه: اقتراب أجل إيداع عرض لصفقة متابعة (AR).",
        langue="ar",
    ),
    "rapport_hebdo_email": Gabarit(
        nom="rapport_hebdo_email",
        canal="email",
        variables=("nom_client", "periode", "nb_appels_offres", "lien_dashboard"),
        description="Rapport hebdomadaire envoyé par email (récapitulatif).",
        langue="fr",
    ),
    "rapport_hebdo_email_fr": Gabarit(
        nom="rapport_hebdo_email_fr",
        canal="email",
        variables=("nom_client", "periode", "nb_appels_offres", "lien_dashboard"),
        description="Rapport hebdomadaire (FR).",
        langue="fr",
    ),
    "rapport_hebdo_email_ar": Gabarit(
        nom="rapport_hebdo_email_ar",
        canal="email",
        variables=("nom_client", "periode", "nb_appels_offres", "lien_dashboard"),
        description="تقرير أسبوعي (AR).",
        langue="ar",
    ),
}


def obtenir_gabarit(nom: str) -> Gabarit | None:
    """Retourne le gabarit par son nom, ou None s'il n'existe pas (= rejeté)."""
    return GABARITS.get(nom)


def variables_autorisees(nom_gabarit: str) -> tuple[str, ...]:
    """Retourne les variables autorisées pour un gabarit donné."""
    gabarit = obtenir_gabarit(nom_gabarit)
    return gabarit.variables if gabarit else ()
