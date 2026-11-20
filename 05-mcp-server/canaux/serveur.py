"""
serveur.py — Point d'entrée du serveur MCP "canaux".

ADR-001 v2.6 : ce serveur est l'UNIQUE passerelle d'émission sortante
(WhatsApp + Email) pour tout le système Sou9na. Expose 3 outils MCP :

  - envoyer_whatsapp    : envoie un message WhatsApp via un gabarit
  - envoyer_email       : envoie un email via un gabarit
  - verifier_templates  : liste les gabarits disponibles (lecture seule)

Transport : stdio (FastMCP) — appelé par les agents (CONCIERGE, etc.)
comme un outil MCP standard, pas comme une API HTTP.
"""

from mcp.server.fastmcp import FastMCP

from client_email import EmailError, envoyer_template_email
from client_whatsapp import WhatsAppError, envoyer_template_whatsapp
from gabarits import GABARITS, obtenir_gabarit
from journal import journaliser_tentative
from securite import SecuriteError, marquer_succes, verifier_envoi

mcp = FastMCP("canaux")


@mcp.tool()
async def envoyer_whatsapp(
    destinataire: str,
    nom_gabarit: str,
    variables: dict[str, str],
    ref: str,
) -> dict:
    """Envoie un message WhatsApp template à un destinataire.

    - destinataire : numéro WhatsApp au format international
    - nom_gabarit   : nom du gabarit (voir verifier_templates)
    - variables     : valeurs des variables du gabarit
    - ref           : identifiant unique de cette demande d'envoi
                      (idempotence — réutiliser le même ref sur un
                      retry ne renverra PAS un 2e message)
    """
    try:
        verifier_envoi(nom_gabarit, variables, destinataire, ref)
    except SecuriteError as exc:
        journaliser_tentative(
            "envoyer_whatsapp", destinataire, nom_gabarit, ref,
            statut="rejet_securite", details=str(exc),
        )
        return {"succes": False, "erreur": str(exc)}

    try:
        resultat = await envoyer_template_whatsapp(destinataire, nom_gabarit, variables)
    except WhatsAppError as exc:
        journaliser_tentative(
            "envoyer_whatsapp", destinataire, nom_gabarit, ref,
            statut="echec_api", details=str(exc),
        )
        return {"succes": False, "erreur": str(exc)}

    marquer_succes(destinataire, ref)
    journaliser_tentative(
        "envoyer_whatsapp", destinataire, nom_gabarit, ref,
        statut="succes", details=str(resultat),
    )
    return {"succes": True, "resultat": resultat}


@mcp.tool()
async def envoyer_email(
    destinataire: str,
    nom_gabarit: str,
    variables: dict[str, str],
    ref: str,
) -> dict:
    """Envoie un email template à un destinataire.

    Mêmes paramètres que envoyer_whatsapp. Contrairement à WhatsApp,
    le remplissage des variables dans le gabarit est fait ICI (en
    Python) avant l'appel à Brevo, car Brevo n'a pas de notion de
    "gabarit canaux" — il reçoit un sujet/corps déjà complets.
    """
    try:
        verifier_envoi(nom_gabarit, variables, destinataire, ref)
    except SecuriteError as exc:
        journaliser_tentative(
            "envoyer_email", destinataire, nom_gabarit, ref,
            statut="rejet_securite", details=str(exc),
        )
        return {"succes": False, "erreur": str(exc)}

    gabarit = obtenir_gabarit(nom_gabarit)
    # TODO(Ayoub) : remplacer par de vrais textes/sujets par gabarit
    # (actuellement un texte générique de démonstration).
    sujet = f"Sou9na — {gabarit.description}"
    corps_html = "<p>" + " ".join(f"{k}: {v}" for k, v in variables.items()) + "</p>"

    try:
        resultat = await envoyer_template_email(destinataire, sujet, corps_html)
    except EmailError as exc:
        journaliser_tentative(
            "envoyer_email", destinataire, nom_gabarit, ref,
            statut="echec_api", details=str(exc),
        )
        return {"succes": False, "erreur": str(exc)}

    marquer_succes(destinataire, ref)
    journaliser_tentative(
        "envoyer_email", destinataire, nom_gabarit, ref,
        statut="succes", details=str(resultat),
    )
    return {"succes": True, "resultat": resultat}


@mcp.tool()
def verifier_templates() -> dict:
    """Liste les gabarits disponibles (lecture seule, pas d'envoi).

    Utile pour qu'un agent appelant sache quels gabarits/variables
    existent avant de tenter un envoi.
    """
    return {
        nom: {
            "canal": g.canal,
            "variables": list(g.variables),
            "description": g.description,
        }
        for nom, g in GABARITS.items()
    }


if __name__ == "__main__":
    mcp.run()
