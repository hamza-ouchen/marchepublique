"""
client_email.py — Envoi d'emails via Gmail SMTP direct.

Remplace client_brevo.py pour la phase de test/soutenance (projet de
fin de formation) : un compte Gmail personnel + App Password permet
d'envoyer des emails fiables SANS domaine propre, car l'email part
réellement des serveurs de Google (pas de rejet DMARC comme avec un
service tiers tel que Brevo utilisant une adresse @gmail.com).

À REMPLACER après la soutenance par un envoi via un domaine propre
authentifié (Brevo + DNS SPF/DKIM/DMARC, voir README) pour la
production réelle.

Nécessite un "App Password" Gmail (pas le mot de passe normal du
compte) — voir https://myaccount.google.com/apppasswords
(2FA doit être activée sur le compte Google).
"""

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailError(Exception):
    """Levée si l'envoi via Gmail SMTP échoue."""


def _config() -> tuple[str, str, str]:
    adresse = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]
    sender_name = os.getenv("GMAIL_SENDER_NAME", "Sou9na")
    return adresse, app_password, sender_name


async def envoyer_template_email(
    destinataire: str,
    sujet: str,
    corps_html: str,
) -> dict:
    """Envoie un email via Gmail SMTP (smtp.gmail.com:465, SSL).

    Mêmes paramètres et même signature que l'ancienne fonction de
    client_brevo.py, pour que serveur.py n'ait presque rien à changer.

    Retourne un petit dict de confirmation (Gmail SMTP ne renvoie pas
    de messageId comme Brevo). Lève EmailError en cas d'échec.
    """
    adresse, app_password, sender_name = _config()

    message = MIMEMultipart("alternative")
    message["Subject"] = sujet
    message["From"] = f"{sender_name} <{adresse}>"
    message["To"] = destinataire
    message.attach(MIMEText(corps_html, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as serveur:
            serveur.login(adresse, app_password)
            serveur.sendmail(adresse, destinataire, message.as_string())
    except smtplib.SMTPException as exc:
        raise EmailError(f"Erreur SMTP Gmail : {exc}") from exc
    except OSError as exc:
        raise EmailError(f"Erreur reseau vers Gmail SMTP : {exc}") from exc

    return {"statut": "envoye", "destinataire": destinataire, "via": "gmail_smtp"}
