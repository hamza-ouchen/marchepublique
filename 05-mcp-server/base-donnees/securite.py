# ═══════════════════════════════════════════════════════════════════
# SOU9NA — MCP base-donnees · sécurité : listes blanches strictes
# Source de vérité : 02-backend/migrations/001_schema_v3.sql (10 tables
# métier) + 003_plateforme.sql (6 tables plateforme) et la matrice
# d'accès v3.1 (11-documentation/matrice-acces-mcp-outils-bdd.md).
#
# Principe : ce qui est listé = autorisé. Ce qui n'est pas listé = rejet.
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations


class ErreurAcces(Exception):
    """Accès hors périmètre : rejet immédiat, jamais silencieux."""


# ── Les 16 tables (colonnes issues du schéma SQL réel) ──────────────
# cle_conflict : clé d'unicité pour l'idempotence (ON CONFLICT) — N7.
TABLES: dict[str, dict] = {
    # ── 10 tables métier (001) ──
    "prospects": {
        "colonnes": {"nom", "email", "whatsapp", "secteur", "taille",
                     "consentement_loi_09_08", "honeypot", "statut"},
        "cle_conflict": ("email",),
    },
    "invitations": {
        "colonnes": {"token", "prospect_id", "company_id", "expire_le", "utilise_le"},
        "cle_conflict": ("token",),
    },
    "entreprises": {
        "colonnes": {"company_id", "user_id", "nom", "email", "whatsapp", "secteur",
                     "region", "capacite_mad", "qualifications", "historique",
                     "canaux_optin", "essai_debut", "statut"},
        "cle_conflict": ("company_id",),
    },
    "tenders": {
        "colonnes": {"reference", "organisme", "objet", "secteur", "region",
                     "montant_mad", "caution_mad", "lots", "qualifications_exigees",
                     "delai_jours", "date_publication", "date_remise",
                     "date_collecte", "statut", "source", "source_url",
                     "mis_a_jour_le"},
        "cle_conflict": ("reference",),
    },
    "scores": {
        "colonnes": {"company_id", "reference", "match_total", "composantes",
                     "points_perdus", "algo_version"},
        "cle_conflict": ("company_id", "reference", "algo_version"),
    },
    "verdicts": {
        "colonnes": {"company_id", "reference", "verdict", "controles",
                     "justifications", "risques_a_verifier"},
        "cle_conflict": ("company_id", "reference"),
    },
    "digests": {
        "colonnes": {"company_id", "jour", "contenu_fr", "contenu_ar",
                     "bandeau", "statut_envoi", "envoye_le"},
        "cle_conflict": ("company_id", "jour"),
    },
    "messages": {
        "colonnes": {"company_id", "prospect_id", "canal", "type", "template",
                     "direction", "texte", "langue", "intention", "citation",
                     "statut_envoi", "hitl", "request_id"},
        "cle_conflict": None,           # journal : pas d'unicité
    },
    "feedback": {
        "colonnes": {"company_id", "reference", "resultat", "motif", "date"},
        "cle_conflict": ("company_id", "reference"),
    },
    "run_logs": {
        "colonnes": {"run_id", "type", "statut", "avis_nouveaux", "rejetes",
                     "doublons", "tokens", "cout_mad", "cloture_le"},
        "cle_conflict": ("run_id",),
    },
    # ── 6 tables plateforme (003) ──
    "utilisateurs": {
        "colonnes": {"company_id", "auth_user_id", "nom", "email", "whatsapp",
                     "role", "statut"},
        "cle_conflict": ("email",),
    },
    "abonnements": {
        "colonnes": {"company_id", "plan", "statut", "essai_fin", "prix_mad",
                     "debute_le", "termine_le"},
        "cle_conflict": ("company_id",),
    },
    "otp_codes": {
        "colonnes": {"canal", "destinataire", "code", "expire_le", "utilise_le",
                     "tentatives"},
        "cle_conflict": None,
    },
    "favoris": {
        "colonnes": {"company_id", "user_id", "reference", "statut_dossier", "note"},
        "cle_conflict": ("company_id", "reference"),
    },
    "notifications": {
        "colonnes": {"company_id", "user_id", "type", "titre", "contenu", "lue"},
        "cle_conflict": None,
    },
    "admins": {
        "colonnes": {"nom", "email", "role", "actif"},
        "cle_conflict": ("email",),
    },
}

# Tables pour lesquelles l'upsert (« mettre_a_jour ») est autorisé.
# Règle : réservé à run_logs (le RÉGISSEUR ouvre puis clôture le run).
UPSERT_AUTORISE: set[str] = {"run_logs"}

# ── Périmètres par appelant (matrice v3.1, §3) ──────────────────────
PERIMETRES: dict[str, dict[str, set[str]]] = {
    "RÉGISSEUR":   {"lit": {"run_logs"},          "ecrit": {"run_logs"}},
    "INSPECTEUR":  {"lit": {"tenders"},           "ecrit": {"tenders"}},
    "COMPAGNON":   {"lit": {"tenders", "entreprises", "feedback", "verdicts",
                            "favoris"},
                    "ecrit": {"scores", "digests"}},
    "JUGE":        {"lit": {"tenders", "entreprises", "scores"},
                    "ecrit": {"verdicts"}},
    "CONCIERGE":   {"lit": {"entreprises", "utilisateurs", "scores", "verdicts",
                            "messages", "digests", "prospects"},
                    "ecrit": {"messages", "feedback", "digests", "notifications"}},
    "SENTINELLE":  {"lit": {"tenders"},           "ecrit": set()},  # alertes_sentinelle = P2
    # Le backend FastAPI gère la couche plateforme (utilisateurs, abonnements,
    # otp_codes, favoris, notifications, admins) + le parcours d'inscription.
    "backend":     {"lit": set(TABLES),           "ecrit": set(TABLES)},
}

LIMITE_MAX = 1000


def valider_appelant(appelant: str) -> dict[str, set[str]]:
    """Retourne le périmètre de l'appelant, sinon rejet."""
    if appelant not in PERIMETRES:
        raise ErreurAcces(
            f"appelant inconnu : {appelant!r} — valeurs autorisées : "
            f"{sorted(PERIMETRES)}"
        )
    return PERIMETRES[appelant]


def valider_table(table: str, appelant: str, sens: str) -> set[str]:
    """Vérifie que l'appelant peut lire/écrire cette table (matrice v3.1).
    Renvoie la liste blanche de colonnes de la table."""
    perimetre = valider_appelant(appelant)
    if table not in TABLES:
        raise ErreurAcces(f"table inconnue : {table!r} — interdite par défaut")
    if table not in perimetre[sens]:
        raise ErreurAcces(
            f"{appelant} ne peut pas {sens} la table {table!r} "
            f"(périmètre : {sorted(perimetre[sens])}) — rejet + alerte observabilité"
        )
    return TABLES[table]["colonnes"]


def valider_colonnes(table: str, colonnes: set[str], sens: str) -> set[str]:
    """Chaque colonne demandée doit figurer dans la liste blanche de la table."""
    defs = TABLES[table]["colonnes"]
    inconnues = colonnes - defs
    if inconnues:
        raise ErreurAcces(
            f"colonnes inconnues pour {table!r} ({sens}) : {sorted(inconnues)} "
            f"autorisées : {sorted(defs)}"
        )
    return defs


def valider_limite(limite: int) -> int:
    """Les lectures sont en batch, mais plafonnées."""
    if not isinstance(limite, int) or limite < 1:
        raise ErreurAcces(f"limite invalide : {limite!r}")
    return min(limite, LIMITE_MAX)
