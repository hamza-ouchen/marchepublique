"""
test_email_reel.py — Script de test manuel : envoie un VRAI email via
Gmail SMTP pour verifier que .env + client_email.py fonctionnent ensemble.

Usage (depuis le dossier canaux/) :
    python test_email_reel.py
"""

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()  # charge les variables depuis .env

from client_email import envoyer_template_email


async def main():
    destinataire = "ayoubabdelmoughit75@gmail.com"

    print(f"Envoi d'un email de test a {destinataire}...")

    resultat = await envoyer_template_email(
        destinataire=destinataire,
        sujet="Sou9na — Test canaux (Gmail SMTP)",
        corps_html="<p>Ceci est un email de test envoye par le serveur MCP <b>canaux</b>.</p>"
                    "<p>Si tu recois ceci, client_email.py (Gmail SMTP) fonctionne correctement.</p>",
    )

    print("Succes ! Resultat :")
    print(resultat)


if __name__ == "__main__":
    asyncio.run(main())
