# 🧰 05-mcp-server — les 3 serveurs MCP de Sou9na

> 👤 Tenue des enveloppes : Hamza Mhalli · Référence : matrice v3.1
> Chaque sous-dossier contient son README détaillé + ses tests.

| Serveur | Outil(s) | Appelé par | Mission |
|---|---|---|---|
| `base-donnees/` | `lire` · `ecrire` | tous les agents (+ backend) | accès Postgres/Supabase, périmètres vérifiés (16 tables) |
| `portail-marches/` | `rechercher_avis(date)` | INSPECTEUR **seulement** | pages brutes du portail, collecte respectueuse |
| `base-connaissances/` | `chercher(requete, corpus)` | JUGE · CONCIERGE | passages cités `{texte, source, article, score}` × 5 |
| `canaux/` *(planifié — Ayoub)* | `envoyer_whatsapp` · `envoyer_email` · `verifier_templates` | COMPAGNON · CONCIERGE | émission sortante (ADR-001) |

> ⚠️ **`canaux` et v2.6** — voir `11-documentation/v2.6/`. `whatsapp/` obsolète

## Démarrage rapide (chaque serveur)

```bash
cd <serveur>
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt
copy .env.example .env            # puis remplir les valeurs LOCALEMENT
.venv/Scripts/python serveur.py   # lit .env automatiquement (stdio par défaut)
# HTTP (StreamableHTTP) — renseigner dans .env :
#   MCP_TRANSPORT=streamable-http
#   FASTMCP_HOST=0.0.0.0
#   FASTMCP_PORT=8201   # 8201 base-donnees · 8202 portail-marches · 8203 base-connaissances
```

## 🌐 **Connexion depuis la plateforme Agentic (Langflow / moteur)**

Les agents du moteur accèdent aux MCP **par URL + Bearer** (comme Coach).
Chaque serveur HTTP expose : `POST http://<hôte>:<port>/mcp` (StreamableHTTP).

**Variable d'environnement à renseigner sur le dashboard / Render** (jamais dans le repo) :

```env
MCP_BASE_DONNEES_URL=https://<tunnel-ou-render>/mcp     # ex. https://abc123.ngrok-free.app/mcp
MCP_PORTAIL_MARCHES_URL=https://<tunnel-ou-render>/mcp
MCP_BASE_CONNAISSANCES_URL=https://<tunnel-ou-render>/mcp
MCP_AUTH_TOKEN=...                                       # UN SEUL jeton pour les 3 serveurs
```

> 🔑 **Un seul jeton** : la même valeur `MCP_AUTH_TOKEN` est mise dans le `.env`
> de chaque serveur et dans le client (RÉGISSEUR, plateforme). Les anciennes
> variables `FASTMCP_AUTH_TOKEN` et `MCP_*_TOKEN` restent lues en repli pour
> compatibilité, mais ne sont plus nécessaires.

**Exposer les 3 serveurs d'un coup avec ngrok** (un seul agent, 3 tunnels) :

```yaml
# ngrok-sou9na.yml — garder ce fichier HORS du repo (il contient l'authtoken)
version: "3"
agent:
  authtoken: <votre-authtoken>
tunnels:
  base-donnees:
    proto: http
    addr: 8201
  portail-marches:
    proto: http
    addr: 8202
  base-connaissances:
    proto: http
    addr: 8203
```

```bash
ngrok start --all --config ngrok-sou9na.yml
# URLs publiques : http://127.0.0.1:4040/api/tunnels
```

**Configuration type d'un serveur MCP distant sur la plateforme (mode « HTTP/Streamable ») :**

```jsonc
{
  "mcpServers": {
    "base-donnees": {
      "type": "streamable-http",
      "url": "https://<tunnel-ou-render>/mcp",
      "headers": { "Authorization": "Bearer <MCP_AUTH_TOKEN>" }
    }
  }
}
```

**Sur la plateforme (dashboard moteur Agentic) :**

1. « **MCP servers** / Intégrations » → « **Add remote MCP** »
2. Type : **HTTP / StreamableHTTP**
3. URL : `https://<tunnel-ou-render>/mcp`
4. Header : `Authorization: Bearer <MCP_AUTH_TOKEN>`
5. Sauver, tester (« test integration »), puis assigner ce serveur aux agents
   concernés (INSPECTEUR pour portail-marches, compgnon… — voir matrice)

**Sans ngrok valide :** déployer sur Render (déjà prévu) ; exposer via
`cloudflared` (tunnel gratuit sans compte) ; sinon rester en local avec
`localhost` (même machine que le moteur — pattern Coach : tout en local).

> ℹ️ **Bearer activé** : dès que `MCP_AUTH_TOKEN` est défini dans le `.env`
> du serveur (même valeur côté plateforme), les requêtes **sans** ce header
> renvoient **HTTP 401**. Sans cette variable, le serveur reste ouvert
> (dev local uniquement).

## Déclaration chez un client MCP (Claude Desktop, LangGraph…)

```json
{
  "mcpServers": {
    "base-donnees":      { "command": "python", "args": ["05-mcp-server/base-donnees/serveur.py"] },
    "portail-marches":   { "command": "python", "args": ["05-mcp-server/portail-marches/serveur.py"] },
    "base-connaissances":{ "command": "python", "args": ["05-mcp-server/base-connaissances/serveur.py"] }
  }
}
```

## Règle d'or

Ce qui est listé dans la matrice (`11-documentation/matrice-acces-mcp-outils-bdd.md`)
= autorisé. **Ce qui n'est pas listé = interdit par défaut.** Toute modification
de périmètre passe par une revue collective (PR).
