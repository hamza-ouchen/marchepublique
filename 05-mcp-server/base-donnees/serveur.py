# ═══════════════════════════════════════════════════════════════════
# SOU9NA — MCP « base-donnees » · serveur (transport stdio)
# Deux outils : lire / ecrire — enveloppe de sécurité, zéro logique métier.
# Références : matrice-acces-mcp-outils-bdd.md v3.1 · securite.py
# ═══════════════════════════════════════════════════════════════════

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Annotated, Any

import psycopg
from pydantic import BaseModel, BeforeValidator, ConfigDict
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
    valider_offset,
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
        if " #" in valeur:
            valeur = valeur.split(" #", 1)[0]
        os.environ.setdefault(cle.strip(), valeur.strip().strip('"').strip("'"))


_charger_env(Path(__file__).with_name(".env"))

_mode = os.environ.get("MCP_TRANSPORT", "stdio")
_port = int(os.environ.get("FASTMCP_PORT", "8201"))
_kwargs = {"host": os.environ.get("FASTMCP_HOST", "127.0.0.1"), "port": _port}
if _mode in ("sse", "streamable-http"):
    # ngrok / réseau : désactiver la protection DNS (hôtes publics du tunnel)
    _kwargs["transport_security"] = TransportSecuritySettings(enable_dns_rebinding_protection=False)

# ── Auth optionnel : si MCP_AUTH_TOKEN est défini, tout transport HTTP
# exige l'en-tête « X-API-Key: <token> » (ou « api-mcp-key »).
# Stdio reste sans auth (usage local). Alias historique : FASTMCP_AUTH_TOKEN.
_auth_token = (
    os.environ.get("MCP_AUTH_TOKEN", "").strip()
    or os.environ.get("FASTMCP_AUTH_TOKEN", "").strip()
)

# ── Middleware d'authentification par clé API (en-tête personnalisé) ──
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Vérifie la clé API dans l'en-tête X-API-Key (ou api-mcp-key)."""

    def __init__(self, app, api_key: str):
        super().__init__(app)
        self.api_key = api_key

    async def dispatch(self, request, call_next):
        if self.api_key and request.url.path != "/":
            key = (
                request.headers.get("x-api-key")
                or request.headers.get("api-mcp-key")
                or request.headers.get("authorization", "").replace("Bearer ", "").strip()
            )
            # Auth required: key must be present and valid (like original design)
            if not key or key != self.api_key:
                return JSONResponse(
                    {"error": "unauthorized", "detail": "Clé API manquante ou invalide"},
                    status_code=401,
                )
        return await call_next(request)

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
    offset: int = 0,
) -> dict:
    """Lit des lignes d'une table autorisée — en batch, plafonné à 1000.

    filtres : {"colonne": valeur} (égalité) — colonne vérifiée contre la
    liste blanche. ordre : "colonne" ou "colonne desc".
    offset : décalage pour parcourir un jeu de données > 1000 lignes.
    """
    try:
        defs = valider_table(table, appelant, "lit")
        limite = valider_limite(limite)
        offset = valider_offset(offset)
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
            f"{(' WHERE ' + where_sql) if where_sql else ''}{order_sql} "
            f"LIMIT {limite} OFFSET {offset}"
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
class LigneEcriture(BaseModel):
    """Ligne d'écriture générique.

    Les colonnes de ``scores`` sont déclarées explicitement afin que les
    clients LLM (Langflow/MCP) voient un schéma d'objet complet au lieu
    d'un ``object`` sans propriétés (qui les amenait à envoyer ``{}``).
    ``extra="allow"`` conserve les colonnes propres aux autres tables.
    """

    model_config = ConfigDict(extra="allow")

    company_id: str | None = None
    reference: str | None = None
    match_total: int | None = None
    composantes: Annotated[Any, BeforeValidator(_parse_dict)] = None
    points_perdus: Annotated[Any, BeforeValidator(_parse_list)] = None
    algo_version: str | None = None


def _parse_dict(v):
    """Accepte un dict ou son encodage JSON en chaîne (tolérance LLM)."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (ValueError, TypeError) as e:
            raise ValueError(f"composantes : JSON invalide ({e})") from e
    return v


def _parse_list(v):
    """Accepte une liste ou son encodage JSON en chaîne (tolérance LLM)."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except (ValueError, TypeError) as e:
            raise ValueError(f"points_perdus : JSON invalide ({e})") from e
    return v


def _parse_lignes(v):
    """Accepte une liste d'objets ou son encodage JSON en chaîne."""
    if isinstance(v, str):
        try:
            return json.loads(v)
        except ValueError as e:
            raise ValueError(f"lignes : JSON invalide ({e})") from e
    return v


Lignes = Annotated[list[LigneEcriture], BeforeValidator(_parse_lignes)]


@mcp.tool()
def ecrire(
    table: str,
    lignes: Lignes,
    appelant: str,
    si_doublon: str = "ignorer",
) -> dict:
    """Écrit des lignes (idempotence N7). si_doublon : "ignorer" (défaut)
    ou "mettre_a_jour" (upsert, réservé à run_logs).
    lignes : liste d'objets, ou tableau JSON sérialisé en chaîne
    (tolérance LLM — désérialisé automatiquement).
    """
    try:
        lignes = [
            ligne.model_dump(exclude_none=True) if isinstance(ligne, LigneEcriture) else ligne
            for ligne in lignes
        ]
        # Journal de diagnostic : que reçoit vraiment l'outil ?
        try:
            import time as _time
            with open(Path(__file__).parent / "_ecrire_calls.log", "a", encoding="utf-8") as _f:
                _f.write(json.dumps({
                    "t": _time.strftime("%Y-%m-%d %H:%M:%S"),
                    "table": table,
                    "appelant": appelant,
                    "lignes_type": type(lignes).__name__,
                    "lignes_head": str(lignes)[:400],
                }, ensure_ascii=False) + "\n")
        except Exception:
            pass
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

        def _valeur_sql(valeur):
            """psycopg3 n'adapte pas dict/list vers jsonb : sérialisation explicite."""
            if isinstance(valeur, (dict, list)):
                return json.dumps(valeur, ensure_ascii=False)
            return valeur

        ecrites, ignorees = 0, 0
        with connexion() as cnx, cnx.cursor() as cur:
            for ligne in lignes:
                cur.execute(sql, [_valeur_sql(ligne.get(c)) for c in ordre_colonnes])
                if cur.rowcount:
                    ecrites += cur.rowcount
                else:
                    ignorees += 1
        return {"table": table, "ecrites": ecrites, "ignorees_doublon": ignorees}
    except ErreurAcces as err:
        return {"erreur": "acces_refuse", "detail": str(err)}


if __name__ == "__main__":
    transport = os.environ.get("MCP_TRANSPORT", "stdio")
    if transport in ("sse", "streamable-http"):
        import uvicorn
        from starlette.applications import Starlette

        # Both transports on one port: /mcp (Streamable HTTP) + /sse (legacy SSE)
        http_app = mcp.streamable_http_app()
        sse_app = mcp.sse_app()
        combined = Starlette(
            routes=list(http_app.routes) + list(sse_app.routes),
            lifespan=http_app.router.lifespan_context,
        )
        combined.add_middleware(APIKeyMiddleware, api_key=_auth_token)
        uvicorn.run(combined, host=_kwargs["host"], port=_kwargs["port"], log_level="info")
    else:
        mcp.run(transport=transport)
