"""
client_whatsapp.py — Appel réel à la WhatsApp Business Cloud API (Meta).

Ce module ne fait AUCUNE vérification de sécurité (ça, c'est le travail
de securite.py, appelé AVANT par serveur.py). Son seul travail : envoyer
un message template déjà validé, et retourner le résultat de Meta.

Doc officielle : https://developers.facebook.com/docs/whatsapp/cloud-api
"""

import os

import httpx


class WhatsAppError(Exception):
    """Levée si l'appel à l'API Meta échoue (réseau, token invalide, etc.)."""


def _config() -> tuple[str, str, str]:
    token = os.environ["WHATSAPP_TOKEN"]
    phone_number_id = os.environ["WHATSAPP_PHONE_NUMBER_ID"]
    api_version = os.getenv("WHATSAPP_API_VERSION", "v21.0")
    return token, phone_number_id, api_version


async def envoyer_template_whatsapp(
    destinataire: str,
    nom_template: str,
    variables: dict[str, str],
) -> dict:
    """Envoie un message template WhatsApp via l'API Graph de Meta.

    - destinataire : numéro au format international, ex. "2126XXXXXXXX"
    - nom_template  : nom EXACT du template approuvé sur Meta Business Manager
    - variables     : valeurs des paramètres du template, DANS L'ORDRE
                      attendu par le template (WhatsApp utilise des
                      paramètres positionnels {{1}}, {{2}}, ... et non
                      des noms de variables).

    Retourne la réponse JSON de Meta (contient entre autres le message id).
    Lève WhatsAppError en cas d'échec HTTP ou de réponse d'erreur de Meta.
    """
    token, phone_number_id, api_version = _config()

    url = f"https://graph.facebook.com/{api_version}/{phone_number_id}/messages"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Les paramètres de template WhatsApp sont positionnels : on respecte
    # l'ordre d'insertion du dict `variables` (Python 3.7+ garde l'ordre).
    parametres = [{"type": "text", "text": str(v)} for v in variables.values()]

    payload = {
        "messaging_product": "whatsapp",
        "to": destinataire,
        "type": "template",
        "template": {
            "name": nom_template,
            "language": {"code": "fr"},  # TODO(Ayoub): rendre dynamique si multi-langue
            "components": [
                {"type": "body", "parameters": parametres}
            ] if parametres else [],
        },
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            reponse = await client.post(url, headers=headers, json=payload)
        except httpx.HTTPError as exc:
            raise WhatsAppError(f"Erreur réseau vers l'API Meta : {exc}") from exc

    if reponse.status_code >= 400:
        raise WhatsAppError(
            f"Meta a refusé l'envoi (HTTP {reponse.status_code}) : {reponse.text}"
        )

    return reponse.json()
