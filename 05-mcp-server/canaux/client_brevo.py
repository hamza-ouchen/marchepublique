"""
client_brevo.py — Appel réel à l'API Brevo (envoi d'emails transactionnels).

Même principe que client_whatsapp.py : ce module ne vérifie RIEN, il
envoie un email déjà validé par securite.py. Son seul travail : parler
à l'API Brevo et retourner le résultat.

Doc officielle : https://developers.brevo.com/reference/sendtransacemail
"""

import os

import httpx


class BrevoError(Exception):
    """Levée si l'appel à l'API Brevo échoue (réseau, clé invalide, etc.)."""


def _config() -> tuple[str, str, str]:
    api_key = os.environ["BREVO_API_KEY"]
    sender_email = os.environ["BREVO_SENDER_EMAIL"]
    sender_name = os.getenv("BREVO_SENDER_NAME", "Sou9na")
    return api_key, sender_email, sender_name


async def envoyer_template_email(
    destinataire: str,
    sujet: str,
    corps_html: str,
) -> dict:
    """Envoie un email transactionnel via l'API Brevo.

    - destinataire : adresse email du destinataire
    - sujet         : sujet de l'email (déjà rempli avec les variables
                       du gabarit, fait par l'appelant avant ce point)
    - corps_html    : corps HTML de l'email (déjà rempli avec les
                       variables du gabarit)

    Retourne la réponse JSON de Brevo (contient le messageId).
    Lève BrevoError en cas d'échec HTTP ou de réponse d'erreur de Brevo.
    """
    api_key, sender_email, sender_name = _config()

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
            raise BrevoError(f"Erreur réseau vers l'API Brevo : {exc}") from exc

    if reponse.status_code >= 400:
        raise BrevoError(
            f"Brevo a refusé l'envoi (HTTP {reponse.status_code}) : {reponse.text}"
        )

    return reponse.json()
