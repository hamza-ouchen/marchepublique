# Sou9na — déploiement production (automatique)

## Démarrage

```bash
docker compose up -d --build
```

Une seule commande démarre :

| Service | Rôle |
|---|---|
| `api` | FastAPI, point d'entrée HTTP (`/cron/run`, `/api/dashboard`, `/api/chat`, `/api/prospects`) |
| `worker` | consomme la file `daily_workflow_jobs` et appelle le RÉGISSEUR |
| `scheduler` | POST `/cron/run` chaque jour à `SOU9NA_CRON_TIME` (défaut 06:00 Casablanca) |
| `regisseur`, `inspecteur`, `compagnon`, `juge` | chaîne A2A réelle |
| `mcp-base-donnees`, `mcp-canaux` | serves MCP avec `X-API-Key` |
| `frontend` | landing + dashboard premium + chatbot (proxy `/api/*` vers FastAPI) |

Aucun redémarrage manuel n'est nécessaire : tous les services ont `restart: unless-stopped`.

## Configuration

Secrets : `02-backend/.env` et `04-langgraph/regisseur/.env` (jamais copiés dans l'image Docker).

Variables importantes (valeurs par défaut dans `docker-compose.yml`) :

```env
SOU9NA_CRON_COMPANY=all          # toutes les entreprises éligibles
SOU9NA_COMPANY_STATUSES=actif,essai
SOU9NA_BATCH_SIZE=1000           # jusqu'à 1000 sociétés par lot
SOU9NA_CRON_TIME=06:00
SOU9NA_CRON_TZ=Africa/Casablanca
MODE_AGENTS=reel
SOU9NA_AGENTIC_FIRST=0         # historique Agentic, hors des entrées actives
SOU9NA_AGENTIC_TIMEOUT=900     # délai des workflows historiques
AGENTIC_JUGE_FLOW_ID=          # identifiant historique
AGENTIC_JUGE_URL=
AGENTIC_JUGE_API_KEY=
SOU9NA_AGENTIC_FLOW=0          # historique Agentic
DOCUMENT_WORKERS=8
DOCUMENT_LIMIT=40
```

En production, poser `SOU9NA_COMPANY_STATUSES=actif` pour ne traiter que les comptes actifs.

Les entrées actives utilisent les agents LangGraph/A2A et le moteur local
de Concierge. Les paramètres et exports Agentic restent disponibles pour
les workflows historiques isolés.

## Ce qui se passe chaque nuit

1. Le scheduler appelle `POST /cron/run` avec `X-Cron-Secret`.
2. FastAPI énumère **toutes** les entreprises éligibles et crée un job par entreprise.
3. Le worker traite les jobs **sérieusement** (un seul scraping du portail par lot :
   `collecte=auto` pour la première société, `collecte=none` pour les suivantes).
4. Pour chaque entreprise, le RÉGISSEUR enchaîne :
   collecte → **collecte des documents PDF** → scoring → verdict → digest → distribution.
   Le scoring et le verdict appellent d'abord les flows Agentic ; en cas de timeout,
   d'erreur HTTP ou de réponse incomplète, ils basculent sur les agents LangGraph/A2A.
5. Les PDF sont téléchargés **avant** le scoring ; le JUGE ne prononce
   `GO` que sur preuve documentaire, sinon `A_ETUDIER` avec confiance faible.
6. Le digest enrichi (risques, confiance, citations) part par email ; WhatsApp reste
   réservé aux demandes à la demande.

## Anti-doublons

- `scrape_portal.py` déduplique par **URL canonique** puis par référence en mémoire,
  pré-filtre la base par lots de 500, puis insert avec `ON CONFLICT (reference) DO NOTHING`.
- L'index `idx_tenders_source_url` (migration `009`) accélère le pré-filtrage.
- Les doublons historiques déjà présents ne sont pas supprimés automatiquement :
  une migration dédiée est requise car des `scores` / `verdicts` / `tender_documents`
  y sont rattachés.

## Vérification rapide

```bash
curl http://127.0.0.1:8000/health
curl -H "X-Cron-Secret: $CRON_SECRET" -X POST \
  'http://127.0.0.1:8000/cron/run?mode=auto'
curl 'http://127.0.0.1:8000/api/dashboard?company_id=EXPLEO-IT-001'
curl -X POST \
  'http://127.0.0.1:8000/api/chat?company_id=EXPLEO-IT-001&message=Quels%20sont%20mes%20risques%20%3F'
```

Le tableau de bord est servi sur `http://localhost:3000/dashboard`.
