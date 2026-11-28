"""Envoi WhatsApp/email pour le concierge Sou9na (contrôle de sécurité inclus).

FastAPI reste le point d'entrée ; ce module n'est qu'un adaptateur de canal.
Aucun LLM, aucune donnée d'une autre entreprise, aucun handoff hors plateforme.
"""
from __future__ import annotations

import html
import json
import os
import smtplib
import urllib.error
import urllib.request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any


def _test_recipient(phone: str) -> bool:
    digits = "".join(ch for ch in phone if ch.isdigit())
    autorises = [d.strip() for d in os.getenv("WHATSAPP_TEST_RECIPIENTS", "").split(",") if d.strip()]
    return any(digits.endswith(d) or d.endswith(digits) for d in autorises)


def send_whatsapp(phone: str, text: str) -> tuple[bool, str]:
    """Message texte Meta Cloud API. Kill switch + liste blanche de test."""
    token = os.getenv("WHATSAPP_TOKEN", "")
    phone_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "")
    if not token or not phone_id:
        return False, "whatsapp_not_configured"
    if os.getenv("KILL_SWITCH", "").lower() in ("1", "true", "oui", "yes") and not _test_recipient(phone):
        return False, "kill_switch_active"

    version = os.getenv("WHATSAPP_API_VERSION", "v21.0")
    url = f"https://graph.facebook.com/{version}/{phone_id}/messages"
    donnees = json.dumps({
        "messaging_product": "whatsapp",
        "to": "".join(ch for ch in phone if ch.isdigit()),
        "type": "text",
        "text": {"preview_url": False, "body": str(text)[:4000]},
    }).encode("utf-8")
    requete = urllib.request.Request(
        url, data=donnees, method="POST",
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(requete, timeout=30) as reponse:
            corps = json.loads(reponse.read().decode("utf-8"))
    except (urllib.error.URLError, ValueError, TimeoutError) as exc:
        return False, f"network:{type(exc).__name__}"

    if corps.get("error"):
        erreur = corps["error"]
        return False, f"meta_{erreur.get('code', 'error')}:{str(erreur.get('message', ''))[:100]}"
    if not corps.get("messages"):
        return False, "meta_rejected_silently"
    return True, "sent"


def send_email(destinataire: str, sujet: str, corps_html: str) -> tuple[bool, str]:
    """SMTP Gmail (port 465 SSL). Le contenu reste 100 % français."""
    adresse = os.getenv("GMAIL_ADDRESS") or os.getenv("SMTP_USER", "")
    mot_de_passe = os.getenv("GMAIL_APP_PASSWORD") or os.getenv("SMTP_PASSWORD", "")
    if not adresse or not mot_de_passe:
        return False, "email_not_configured"
    expediteur = os.getenv("SMTP_FROM") or adresse
    nom = os.getenv("GMAIL_SENDER_NAME", "Sou9na")

    message = MIMEMultipart("alternative")
    message["Subject"] = sujet
    message["From"] = f"{nom} <{expediteur}>"
    message["To"] = destinataire
    message.attach(MIMEText(corps_html, "html", "utf-8"))
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=20) as serveur:
            serveur.login(adresse, mot_de_passe)
            serveur.sendmail(expediteur, [destinataire], message.as_string())
    except (smtplib.SMTPException, OSError) as exc:
        return False, f"smtp:{type(exc).__name__}:{str(exc)[:120]}"
    return True, "sent"


def digest_html(prenom: str, lignes: list[str]) -> str:
    elements = "".join(f"<li>{html.escape(ligne)}</li>" for ligne in lignes)
    return (
        "<div style='font-family:Arial,sans-serif;max-width:640px'>"
        f"<h2>Bonjour {html.escape(prenom)},</h2>"
        "<p>Voici votre sélection quotidienne Sou9na. Chaque opportunité comporte "
        "un Match, un verdict et les points à vérifier avant toute décision.</p>"
        f"<ul>{elements or '<li>Aucune opportunité retenue aujourd’hui.</li>'}</ul>"
        "<p>Ces informations sont indicatives : seules les pièces officielles "
        "du dossier font foi.</p></div>"
    )


def trace(route: str, outcome: str, message_id: str = "", sender: str = "",
          error: str | None = None, logs: list[dict[str, Any]] | None = None) -> None:
    """Écrit la trace dans lg_requests / lg_logs si le schéma est présent."""
    from chat import db_cps  # import local pour éviter un cycle
    try:
        request_id = db_cps.query_write(
            "INSERT INTO lg_requests (message_id, sender_phone, route, outcome, error, finished_at, latency_ms) "
            "VALUES (%s,%s,%s,%s,%s,now(),0) RETURNING id::text AS id",
            (message_id or None, sender or None, route, outcome, error),
        )[0]["id"]
        for entree in logs or []:
            db_cps.execute(
                "INSERT INTO lg_logs (request_id, agent, duration_s, detail) VALUES (%s,%s,%s,%s)",
                (request_id, entree.get("agent", "?"), entree.get("duration_s", 0),
                 str(entree.get("detail", ""))[:500]),
            )
    except Exception as exc:
        import logging
        logging.getLogger("sou9na.canaux").warning("trace indisponible : %s", exc)
