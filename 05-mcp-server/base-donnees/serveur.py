# ═══════════════════════════════════════════════════════════════════
# SOU9NA — MCP « base-donnees » · serveur (transport stdio)
# Deux outils : lire / ecrire — enveloppe de sécurité, zéro logique métier.
# Références : matrice-acces-mcp-outils-bdd.md v3.1 · securite.py
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import os
from pathlib import Path

import psycopg
from mcp.server.auth.provider import AccessToken
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from mcp.server.auth.settings import AuthSettings

from securite import (
    TABLES,
    ErreurAcces,
    UPSERT_AUTORISE,
    valider_appelant,
    valider_colonnes,
    valider_limite,
    valider_table,
)


def _charger_env(chemin: Path) -> None:
    """Charge .env sans jamais écraser une variable déjà définie."""
    if not chemin.exists():
        return
    for brute in chemin.read_text(encoding="utf-8-sig").splitlines():
        ligne = brute.strip()
        if not ligne or ligne.startswith("#") or "=" not in ligne:
            continue
        cle, valeur = ligne.split("=", 1)
        os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


_charger_env(Path(__file__).with_name(".env"))

_mode = os.environ.get("MCP_TRANSPORT", "stdio")
_port = int(os.environ.get("FASTMCP_PORT", "8201"))
_kwargs = {"host": os.environ.get("FASTMCP_HOST", "127.0.0.1"), "port": _port}
if _mode in ("sse", "streamable-http"):
    # ngrok / réseau : désactiver la protection DNS (hôtes publics du tunnel)
    _kwargs["transport_security"] = TransportSecuritySettings(enable_dns_rebinding_protection=False)

# ── Auth optionnel : si MCP_AUTH_TOKEN est défini, tout transport HTTP
# exige « Authorization: Bearer <token> » (la plateforme y met son header).
# Stdio reste sans auth (usage local). Alias historique : FASTMCP_AUTH_TOKEN.
_auth_token = (
    os.environ.get("MCP_AUTH_TOKEN", "").strip()
    or os.environ.get("FASTMCP_AUTH_TOKEN", "").strip()
)

class _StaticTokenVerifier:
    """Vérifie un bearer token statique (séquence interne)."""
    def __init__(self, token: str):
        self._token = token
    async def verify_token(self, token: str):
        if self._token and token == self._token:
            return AccessToken(token=token, client_id="sou9na-platform",
                               scopes=["mcp"], resource=None)
        return None

if _mode in ("sse", "streamable-http") and _auth_token:
    _kwargs["token_verifier"] = _StaticTokenVerifier(_auth_token)
    _kwargs["auth"] = AuthSettings(
        issuer_url=f"http://127.0.0.1:{_port}/",
        required_scopes=["mcp"],
        resource_server_url=f"http://127.0.0.1:{_port}/",
    )

mcp = FastMCP("base-donnees", **_kwargs)

# L'URL vient de l'environnement (`.env` local, jamais committé).
DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    raise SystemExit(
        "DATABASE_URL manquant — copiez .env.example en .env "
        "et exportez la variable (pooler Supabase, port 6543)."
    )


def connexion() -> psycopg.Connection:
    """Une connexion courte par appel — adapté au pooler en mode transaction.

    prepare_threshold=None : sans prepared statements (PgBouncer transaction
    mode ne les garde pas entre les sessions).
    """
    return psycopg.connect(
        DATABASE_URL, autocommit=True, prepare_threshold=None, connect_timeout=15
    )


def _sens_sql(table: str, colonnes: set[str]) -> str:
    """Identificateurs sécurisés (déjà validés par la liste blanche)."""
    return ", ".join(f'"{table}"."{c}"' for c in colonnes)


# ─────────────────────────────────────────────────────────────────
# Outil 1 : lire(table, filtres, limite, ordre, appelant)
# ─────────────────────────────────────────────────────────────────
@mcp.tool()
def lire(
    table: str,
    appelant: str,
    filtres: dict | None = None,
    limite: int = 500,
    ordre: str | None = None,
) -> dict:
    """Lit des lignes d'une table autorisée — en batch, plafonné à 1000.

    filtres : {"colonne": valeur} (égalité) — colonne vérifiée contre la
    liste blanche. ordre : "colonne" ou "colonne desc".
    """
    try:
        defs = valider_table(table, appelant, "lit")
        limite = valider_limite(limite)
        filtres = filtres or {}
        valider_colonnes(table, set(filtres), "filtre de lecture")

        where_sql, params = "", []
        if filtres:
            where_sql = " AND ".join(f'"{table}"."{c}" = %s' for c in filtres)
            params = list(filtres.values())

        order_sql = ""
        if ordre:
            colonne, _, sens = ordre.partition(" ")
            valider_colonnes(table, {colonne}, "ordre")
            if sens and sens != "desc":
                raise ErreurAcces(f"ordre invalide : {ordre!r} (ex. 'date_collecte desc')")
            order_sql = f' ORDER BY "{table}"."{colonne}" {sens}'.rstrip()

        sql = (
            f'SELECT {_sens_sql(table, defs)} FROM "{table}"'
            f"{(' WHERE ' + where_sql) if where_sql else ''}{order_sql} LIMIT {limite}"
        )
        with connexion() as cnx, cnx.cursor() as cur:
            cur.execute(sql, params)
            colonnes = [d[0] for d in cur.description]
            lignes = [dict(zip(colonnes, ligne)) for ligne in cur.fetchall()]
        return {"table": table, "nombre": len(lignes), "lignes": lignes}
    except ErreurAcces as err:
        return {"erreur": "acces_refuse", "detail": str(err)}


# ─────────────────────────────────────────────────────────────────
# Outil 2 : ecrire(table, lignes, si_doublon, appelant)
# ─────────────────────────────────────────────────────────────────
@mcp.tool()
def ecrire(
    table: str,
    lignes: list[dict],
    appelant: str,
    si_doublon: str = "ignorer",
) -> dict:
    """Écrit des lignes (idempotence N7). si_doublon : "ignorer" (défaut)
    ou "mettre_a_jour" (upsert, réservé à run_logs).
    """
    try:
        defs = valider_table(table, appelant, "ecrit")
        if si_doublon not in ("ignorer", "mettre_a_jour"):
            raise ErreurAcces(f"si_doublon invalide : {si_doublon!r}")
        if si_doublon == "mettre_a_jour" and table not in UPSERT_AUTORISE:
            raise ErreurAcces(
                f"upsert interdit pour {table!r} — réservé à {sorted(UPSERT_AUTORISE)}"
            )
        if not isinstance(lignes, list) or not lignes:
            raise ErreurAcces("lignes : liste non vide attendue")

        colonnes_utilisees: set[str] = set()
        for ligne in lignes:
            colonnes_utilisees |= set(ligne)
        valider_colonnes(table, colonnes_utilisees, "écriture")

        cle = TABLES[table]["cle_conflict"]
        ordre_colonnes = sorted(colonnes_utilisees)
        placeholders = ", ".join("%s" for _ in ordre_colonnes)
        noms_sql = ", ".join(f'"{c}"' for c in ordre_colonnes)

        if cle:
            cible = ", ".join(f'"{c}"' for c in cle)
            conflit = f"ON CONFLICT ({cible}) DO NOTHING"
            if si_doublon == "mettre_a_jour":
                maj = ", ".join(f'"{c}" = EXCLUDED."{c}"' for c in ordre_colonnes)
                conflit = f"ON CONFLICT ({cible}) DO UPDATE SET {maj}"
        else:
            conflit = ""

        sql = f'INSERT INTO "{table}" ({noms_sql}) VALUES ({placeholders}) {conflit}'.strip()
        ecrites, ignorees = 0, 0
        with connexion() as cnx, cnx.cursor() as cur:
            for ligne in lignes:
                cur.execute(sql, [ligne.get(c) for c in ordre_colonnes])
                if cur.rowcount:
                    ecrites += cur.rowcount
                else:
                    ignorees += 1
        return {"table": table, "ecrites": ecrites, "ignorees_doublon": ignorees}
    except ErreurAcces as err:
        return {"erreur": "acces_refuse", "detail": str(err)}


if __name__ == "__main__":
    # stdio (défaut) ; HTTP/StreamableHTTP sur FASTMCP_PORT (exposé via ngrok) :
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    mcp.run(transport=transport)
