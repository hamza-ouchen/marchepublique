"""
client_brevo.py — Envoi d'emails transactionnels.

Deux voies (comme soukna) :
  1. Brevo API HTTPS (production) — prioritaire si BREVO_API_KEY est défini.
  2. SMTP classique (local/test) — fallback si Brevo absent (Gmail, etc.).

Même contrat : lève BrevoError en cas d'échec.
"""

from __future__ import annotations

import asyncio
import os
import smtplib
from email.mime.text import MIMEText

import httpx


class BrevoError(Exception):
    """Levée si l'envoi email échoue (réseau, clé invalide, SMTP, etc.)."""


def _config_brevo() -> tuple[str, str, str] | None:
    api_key = os.getenv("BREVO_API_KEY")
    sender_email = os.getenv("BREVO_SENDER_EMAIL")
    if not api_key or not sender_email:
        return None
    sender_name = os.getenv("BREVO_SENDER_NAME", "Sou9na")
    return api_key, sender_email, sender_name


def _config_smtp() -> tuple[str, int, str, str, str] | None:
    host = os.getenv("SMTP_HOST")
    if not host:
        return None
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASSWORD", "")
    sender = os.getenv("SMTP_FROM", user or "soukna@noreply.ma")
    return host, port, user, password, sender


async def envoyer_template_email(
    destinataire: str,
    sujet: str,
    corps_html: str,
) -> dict:
    """Envoie un email (HTML) via Brevo API ou SMTP (fallback).

    Retourne un dict avec le messageId / statut.
    Lève BrevoError en cas d'échec.
    """
    # 1. Brevo API (prioritaire)
    brevo = _config_brevo()
    if brevo is not None:
        api_key, sender_email, sender_name = brevo
        url = "https://api.brevo.com/v3/smtp/email"
        headers = {
            "api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "sender": {"name": sender_name, "email": sender_email},
            "to": [{"email": destinataire}],
            "subject": sujet,
            "htmlContent": corps_html,
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            try:
                reponse = await client.post(url, headers=headers, json=payload)
            except httpx.HTTPError as exc:
                raise BrevoError(f"Erreur réseau Brevo : {exc}") from exc
        if reponse.status_code >= 400:
            raise BrevoError(
                f"Brevo a refusé l'envoi (HTTP {reponse.status_code}) : {reponse.text}"
            )
        return reponse.json()

    # 2. SMTP fallback
    smtp = _config_smtp()
    if smtp is not None:
        host, port, user, password, sender = smtp
        def _smtp_send() -> dict:
            msg = MIMEText(corps_html, "html", "utf-8")
            msg["Subject"] = sujet
            msg["From"] = sender
            msg["To"] = destinataire
            try:
                if port == 465:
                    with smtplib.SMTP_SSL(host, port, timeout=30) as server:
                        if user:
                            server.login(user, password)
                        server.sendmail(sender, [destinataire], msg.as_string())
                else:
                    with smtplib.SMTP(host, port, timeout=30) as server:
                        server.starttls()
                        if user:
                            server.login(user, password)
                        server.sendmail(sender, [destinataire], msg.as_string())
            except (smtplib.SMTPException, OSError) as exc:
                raise BrevoError(f"SMTP échec : {exc}") from exc
            return {"messageId": "smtp-sent", "via": "smtp"}
        return await asyncio.to_thread(_smtp_send)

    raise BrevoError(
        "Aucun canal email configuré : définir BREVO_API_KEY ou SMTP_HOST dans .env"
    )
