"""
gabarits.py — Registre des gabarits (templates) autorisés pour canaux.

Principe (ADR-001 / brief §3.1) : AUCUN texte libre n'est jamais envoyé.
Chaque message WhatsApp ou Email envoyé par canaux doit correspondre à
un gabarit de cette liste, avec UNIQUEMENT les variables déclarées ici.

Deux jeux de noms coexistent (fusion develop + feat/canaux du 20/11/2026) :
- noms OFFICIELS du brief §3.1 : digest, conversation, invitation_7j,
  bienvenue, alerte_hitl (utilisés par securite.py / les tests) ;
- noms de test / FR-AR hérités du serveur HTTP : hello_world,
  digest_quotidien[_fr|_ar], alerte_deadline[_fr|_ar],
  rapport_hebdo_email[_fr|_ar] (utilisés par les tests réels Brevo/WhatsApp).

Chaque gabarit déclare :
- appelants    : quels agents ont le droit d'utiliser ce gabarit
                 (whitelist — tout autre appelant = acces_refuse)
- canaux       : sur quel(s) canal/canaux ce gabarit peut être envoyé
- canal        : canal principal (rétro-compatibilité avec l'ancien code)
- variables    : liste des noms de variables autorisées
- description  : à quoi sert ce gabarit (pour audit humain)
- langue       : code langue Meta (fr, ar, en_US, ...)
"""

from dataclasses import dataclass, field
from typing import Literal

Appelant = Literal["CONCIERGE", "COMPAGNON"]
Canal = Literal["whatsapp", "email"]


@dataclass(frozen=True)
class Gabarit:
    nom: str
    variables: tuple[str, ...]
    description: str
    appelants: tuple[Appelant, ...] = ("CONCIERGE", "COMPAGNON")
    canaux: tuple[Canal, ...] = ("whatsapp",)
    langue: str = "fr"

    @property
    def canal(self) -> Canal:
        """Canal principal (rétro-compatibilité : `gabarit.canal`)."""
        return self.canaux[0]


# Variables partagées
_VARS_DIGEST = ("nom_client", "nb_appels_offres", "lien_dashboard", "corps_html", "sujet")
_VARS_DEADLINE = ("nom_client", "titre_appel_offre", "date_limite")
_VARS_RAPPORT = ("nom_client", "periode", "nb_appels_offres", "lien_dashboard")


# --- Registre des gabarits autorisés (whitelist) -------------------------

GABARITS: dict[str, Gabarit] = {
    # --- noms officiels (brief §3.1) ---
    "digest": Gabarit(
        nom="digest",
        appelants=("COMPAGNON",),
        canaux=("whatsapp", "email"),
        variables=_VARS_DIGEST,
        description="Résumé quotidien des appels d'offres pertinents pour un client (COMPAGNON, WhatsApp principal + email de secours).",
    ),
    "conversation": Gabarit(
        nom="conversation",
        appelants=("CONCIERGE",),
        canaux=("whatsapp",),
        variables=("variable_1", "variable_2", "variable_3"),
        description="Réponse conversationnelle de CONCIERGE (FAQ/dossier) — PLACEHOLDER à aligner sur le template Meta approuvé.",
    ),
    "invitation_7j": Gabarit(
        nom="invitation_7j",
        appelants=("CONCIERGE",),
        canaux=("whatsapp", "email"),
        variables=("nom_client", "lien_activation", "date_expiration"),
        description="Invitation (valable 7 jours) après approbation HITL 1 — PLACEHOLDER.",
    ),
    "bienvenue": Gabarit(
        nom="bienvenue",
        appelants=("CONCIERGE",),
        canaux=("whatsapp", "email"),
        variables=("nom_client", "lien_dashboard"),
        description="Message de bienvenue après activation du compte — PLACEHOLDER.",
    ),
    "alerte_hitl": Gabarit(
        nom="alerte_hitl",
        appelants=("CONCIERGE",),
        canaux=("whatsapp",),
        variables=_VARS_DEADLINE,
        description="Alerte : un dossier À ÉTUDIER nécessite une vérification humaine (HITL 2).",
    ),

    # --- noms de test / FR-AR (serveur HTTP, tests réels) ---
    "hello_world": Gabarit(
        nom="hello_world",
        canaux=("whatsapp",),
        variables=(),
        description="Template de test Meta (hello_world) — présent par défaut sur tout compte WhatsApp Business.",
        langue="en_US",
    ),
    "digest_quotidien": Gabarit(
        nom="digest_quotidien",
        variables=_VARS_DIGEST,
        description="Résumé quotidien des appels d'offres pertinents pour un client.",
        langue="fr",
    ),
    "digest_quotidien_fr": Gabarit(
        nom="digest_quotidien_fr",
        variables=_VARS_DIGEST,
        description="Résumé quotidien des appels d'offres pertinents pour un client (FR).",
        langue="fr",
    ),
    "digest_quotidien_ar": Gabarit(
        nom="digest_quotidien_ar",
        variables=_VARS_DIGEST,
        description="ملخص يومي لصفقات المناقصات ذات الصلة للعميل (AR).",
        langue="ar",
    ),
    "alerte_deadline": Gabarit(
        nom="alerte_deadline",
        variables=_VARS_DEADLINE,
        description="Alerte : une échéance de dépôt approche pour un appel d'offres suivi.",
        langue="fr",
    ),
    "alerte_deadline_fr": Gabarit(
        nom="alerte_deadline_fr",
        variables=_VARS_DEADLINE,
        description="Alerte : une échéance de dépôt approche (FR).",
        langue="fr",
    ),
    "alerte_deadline_ar": Gabarit(
        nom="alerte_deadline_ar",
        variables=_VARS_DEADLINE,
        description="تنبيه: اقتراب أجل إيداع عرض لصفقة متابعة (AR).",
        langue="ar",
    ),
    "rapport_hebdo_email": Gabarit(
        nom="rapport_hebdo_email",
        canaux=("email",),
        variables=_VARS_RAPPORT,
        description="Rapport hebdomadaire envoyé par email (récapitulatif).",
        langue="fr",
    ),
    "rapport_hebdo_email_fr": Gabarit(
        nom="rapport_hebdo_email_fr",
        canaux=("email",),
        variables=_VARS_RAPPORT,
        description="Rapport hebdomadaire (FR).",
        langue="fr",
    ),
    "rapport_hebdo_email_ar": Gabarit(
        nom="rapport_hebdo_email_ar",
        canaux=("email",),
        variables=_VARS_RAPPORT,
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
