# 🧭 RÉGISSEUR — l'orchestrateur LangGraph de Sou9na « La Régie »

> 👤 Hamza Mhalli · dossier `04-langgraph/regisseur/`
> Références : README v2.5 §4 · matrice v3.1 §5 · doc coloré v4 (CAS A)

## Mission

Router et superviser — **il ne touche aucune donnée métier** : il écrit
seulement dans `run_logs` (ouverture / clôture) et ordonne les agents.
Les données circulent **via la base**, jamais d'agent à agent.

## Le graphe (la chaîne du matin, CAS A)

```
START
  → porte_valider       (gate 1 — structure : mode, date ISO, run_id)
  → porte_sanitariser   (gate 2 — contenu : longueur, injection heuristique)
  → porte_intention     (gate 3 — intention : mots-clés, hors_perimetre par défaut)
  → ouvrir_run          (RÉGISSEUR : run_logs = « ouvert »)
  → collecter           (INSPECTEUR — 6h05 : portail → tenders)
  → calculer_scores     (COMPAGNON — 6h20 : Match /100, zéro LLM → scores)
  → statuer             (JUGE — 7h00 : verdicts au-dessus du seuil → verdicts)
  → composer_digest     (COMPAGNON — 7h30 : lit scores + verdicts → digests)
  → distribuer          (COMPAGNON — 8h00 : via MCP `canaux` — ADR v2.6)
  → cloturer_run        (RÉGISSEUR : run_logs = « clôturé » / « échec »)
END
```

Règle : une porte qui échoue **rejette AVANT toute logique** — les agents ne
voient jamais une entrée malformée, injectée, ou non autorisée. Chaque porte est
**déterministe** (0 LLM), journalise son passage dans `gates` de l'état,
et débranche vers `rejet_gate` → END si rejet. Toute étape métier qui voit
`erreurs` sauterait aussi, garde-fou inclus.

### Modes

| Mode | Ce qui change | Quand |
|---|---|---|
| `cron` | chaîne complète ci-dessus | 6h00 (POST /cron/run) |
| `manuel` | identique, déclenché par un admin (`POST /run`) | à la demande |
| `backfill` | INSPECTEUR collecte **tous** les avis encore ouverts (une seule fois, avant le cron) | jour du lancement |

### Secours (mode demo)

Tant que les agents ne sont pas branchés (ou pour les tests), le graphe tourne
en **mode demo** : chaque agent renvoie un *rapport simulé* cohérent, le graphe
exécute la chaîne complète de bout en bout — parfait pour valider l'orchestration
avant le code des agents.

## Communication avec les agents et la base

- **Agents (A2A)** : le RÉGISSEUR cherche d'abord une **Agent Card** exposant la
  compétence dont il a besoin (`a2a_client.py` — cartes dans
  `03-agentic-ai/agent-cards/`), puis appelle l'agent en JSON-RPC `message/send`
  avec le header `X-Internal-Token` (`A2A_TOKEN`). Mode `demo` : rapports
  simulés, zéro réseau. Mode `reel` : agent indisponible = **erreur brute**,
  jamais un rapport simulé — le run finit « echec ». URL d'un agent surchargeable
  sans toucher les cartes (`A2A_URL_OVERRIDE_<NOM>` — voir `.env.example`).
- **Base de données** : uniquement via le serveur MCP `base-donnees`
  (`05-mcp-server/base-donnees/`) — `client_mcp.py` lance le serveur en
  sous-processus (transport stdio) et appelle `lire` / `ecrire` avec
  `appelant="RÉGISSEUR"`. Le MCP vérifie le périmètre (matrice v3.1).

## Démarrage

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

# Variables d'environnement (voir .env.example) :
#   DATABASE_URL — pooler Supabase (obligatoire pour les écritures réelles)
#   A2A_TOKEN    — token partagé pour appeler les agents (et pour être appelé)

# Run quotidien (demo, sans agents branchés) :
.venv/Scripts/python run.py --mode cron --demo
# Run réel (les agents sont appelés via A2A, cartes requises) :
.venv/Scripts/python run.py --mode cron
# Backfill du jour de lancement :
.venv/Scripts/python run.py --mode backfill

# Exposer l'agent pour les autres services (FastAPI, nœuds A2A) :
.venv/Scripts/python serveur_http.py     # POST http://0.0.0.0:8100/
```

### Appeler le RÉGISSEUR par HTTP (A2A — JSON-RPC `message/send`)

```bash
curl -X POST http://localhost:8100/ \
  -H "Content-Type: application/json" \
  -H "X-Internal-Token: $A2A_TOKEN" \
  -d '{"jsonrpc":"2.0","id":"1","method":"message/send",
       "params":{"message":{"role":"user","parts":[
         {"kind":"data","data":{"mode":"cron","date":"2026-11-18"}}]}}}'
```

Le skill `orchestrer` de `regisseur.agent-card.json` expose cette signature.

## Tests (zéro réseau, zéro base — client MCP remplacé par un double)

```bash
.venv/Scripts/python -m pytest tests/ -v
```
