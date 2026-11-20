"""
client_email.py — Envoi d'emails via Gmail SMTP (test/soutenance)
avec repli automatique sur Brevo si les identifiants Gmail sont absents.

Le PR feat/canaux a remplacé client_brevo.py par un envoi Gmail SMTP
direct (fiable sans domaine propre). Les identifiants Gmail
(GMAIL_ADDRESS / GMAIL_APP_PASSWORD) ne sont pas toujours présents —
dans ce cas on retombe sur la voie Brevo déjà configurée dans .env,
qui utilise la même signature envoyer_template_email(destinataire,
sujet, corps_html) -> dict.
"""

from __future__ import annotations

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText


class EmailError(Exception):
    """Levée si l'envoi email échoue (Gmail ou Brevo)."""


def _config_gmail() -> tuple[str, str, str] | None:
    adresse = os.getenv("GMAIL_ADDRESS")
    app_password = os.getenv("GMAIL_APP_PASSWORD")
    if not adresse or not app_password:
        return None
    sender_name = os.getenv("GMAIL_SENDER_NAME", "Sou9na")
    return adresse, app_password, sender_name


def _envoyer_gmail(destinataire: str, sujet: str, corps_html: str,
                   config: tuple[str, str, str]) -> dict:
    adresse, app_password, sender_name = config
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


async def _envoyer_brevo(destinataire: str, sujet: str, corps_html: str) -> dict:
    """Repli Brevo (déjà utilisé et validé dans ce projet)."""
    try:
        from client_brevo import envoyer_template_email as envoyer_brevo
        return await envoyer_brevo(destinataire, sujet, corps_html)
    except ImportError as exc:
        raise EmailError("Repli Brevo indisponible (client_brevo.py absent)") from exc


async def envoyer_template_email(destinataire: str, sujet: str, corps_html: str) -> dict:
    """Envoie un email HTML via Gmail SMTP, ou Brevo en repli.

    Même signature que client_brevo.py pour que serveur.py n'ait rien à
    changer. Lève EmailError en cas d'échec.
    """
    gmail = _config_gmail()
    if gmail is not None:
        return _envoyer_gmail(destinataire, sujet, corps_html, gmail)
    return await _envoyer_brevo(destinataire, sujet, corps_html)
