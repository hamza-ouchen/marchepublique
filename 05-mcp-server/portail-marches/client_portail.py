# ═══════════════════════════════════════════════════════════════════
# SOU9NA — MCP portail-marches · client HTTP respectueux du portail
# Règles (obligatoires) : robots.txt · débit limité · identification
# transparente · repli propre si le portail est en panne.
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
import time
from urllib.parse import quote, urljoin
from urllib.robotparser import RobotFileParser

import httpx

# ── Configuration (variables d'environnement) ──────────────────────
MODE = os.environ.get("PORTAIL_MODE", "demo")
BASE_URL = os.environ.get("PORTAIL_BASE_URL", "https://www.marchespublics.gov.ma")
DELAI_S = float(os.environ.get("DELAI_ENTRE_APPELS_S", "2"))
CONTACT = os.environ.get("CONTACT_BOT", "contact@sou9na.ma")

USER_AGENT = f"Sou9naBot/1.0 (+{CONTACT})"

# Timestamp du dernier appel — pour le débit limité.
_dernier_appel = 0.0


def _attendre_delai() -> None:
    """Débit limité : jamais deux requêtes plus vite que DELAI_S."""
    global _dernier_appel
    pause = DELAI_S - (time.time() - _dernier_appel)
    if pause > 0:
        time.sleep(pause)
    _dernier_appel = time.time()


def robots_autorise(chemin: str) -> bool:
    """robots.txt du portail — si illisible, on refuse (par excès de prudence)."""
    try:
        parser = RobotFileParser()
        parser.set_url(urljoin(BASE_URL, "/robots.txt"))
        parser.read()
        return parser.can_fetch(USER_AGENT, urljoin(BASE_URL, chemin))
    except Exception:
        return False


def rechercher_avis_portail(date_iso: str) -> dict:
    """Appel réel du portail — pages brutes pour la date donnée.

    Ce client ne parse rien : il ramène le HTML. L'extraction structurée
    (référence, organisme, montant…) est le travail d'INSPECTEUR.
    """
    if not robots_autorise("/"):
        return {"erreur": "robots_interdit",
                "detail": "robots.txt du portail interdit ce chemin — collecte refusée"}

    # Page de recherche « avis d'appels d'offres » filtrée par date de publication.
    chemin = (
        "/index.php/x/avis-dappels-doffres?"
        f"filter_mode_dacces_par_mot_cle=&zone=all&departement=&date_debut="
        f"{quote(date_iso)}&date_fin={quote(date_iso)}"
    )
    url = urljoin(BASE_URL, chemin)

    try:
        _attendre_delai()
        with httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=30,
            follow_redirects=True,
        ) as client:
            reponse = client.get(url)
            reponse.raise_for_status()
            return {
                "date": date_iso,
                "source": "portail",
                "pages": [{"url": url, "contenu": reponse.text}],
            }
    except httpx.HTTPStatusError as err:
        return {"erreur": "portail_erreur_http", "detail": f"HTTP {err.response.status_code}"}
    except httpx.HTTPError as err:
        # Panne documentée (oct.–nov. 2026) → INSPECTEUR bascule en mode secours.
        return {"erreur": "portail_indisponible", "detail": str(err)}


def rechercher_avis_demo(date_iso: str) -> dict:
    """Mode demo : fixtures locales — zéro réseau, idéal CI / tests."""
    return {
        "date": date_iso,
        "source": "demo",
        "pages": [
            {
                "url": f"fixture://avis/{date_iso}/001",
                "contenu": (
                    "AVIS D'APPEL D'OFFRES OUVERT N°2026/DTR/0123 — Commune de "
                    "Sidi X (Casa-Settat) — objet : travaux d'extension du réseau "
                    "d'éclairage public — montant estimé : 1 500 000 MAD — "
                    "caution provisoire : 30 000 MAD — délai : 120 jours — "
                    "qualification : catégorie C — remise des plis avant le "
                    f"{date_iso} à 10h00."
                ),
            },
            {
                "url": f"fixture://avis/{date_iso}/002",
                "contenu": (
                    "AVIS D'APPEL D'OFFRES OUVERT N°2026/DTR/0124 — Agence "
                    "urbaine (Rabat-Salé-Kénitra) — objet : acquisition de "
                    "solutions informatiques et services numériques — montant "
                    "estimé : 950 000 MAD — caution provisoire : 20 000 MAD — "
                    "délai : 90 jours — qualifications exigées : ISO 9001 — "
                    f"remise des plis avant le {date_iso} à 15h00."
                ),
            },
            {
                "url": f"fixture://avis/{date_iso}/003",
                "contenu": (
                    "AVIS D'ATTRIBUTION N°2026/DTR/0125 — Office régional "
                    "(Souss-Massa) — objet : transport de marchandises — attribué "
                    "à la société Y pour 2 100 000 MAD (archive — SENTINELLE P2)."
                ),
            },
        ],
    }


def rechercher(date_iso: str, mode: str | None = None) -> dict:
    """Point d'entrée unique : mode réel ou demo selon la configuration."""
    mode = mode or MODE
    if mode == "demo":
        return rechercher_avis_demo(date_iso)
    return rechercher_avis_portail(date_iso)
