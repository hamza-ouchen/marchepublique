# 🗄️ MCP `base-donnees` — accès contrôlé à Postgres / Supabase

> **Règle n°1** : ce qui est listé ici = autorisé. Ce qui n'est pas listé = **interdit
> par défaut**. Toute modification passe par une revue collective (PR).
>
> Références : `matrice-acces-mcp-outils-bdd.md` v3.1 · README §4 (contrat d'agent)

## Mission

Exposer **deux outils** (et seulement deux) qui lisent et écrivent dans la base
Supabase (16 tables), **en vérifiant le périmètre de chaque appelant** :
un agent ne peut toucher que les tables de sa ligne dans la matrice.

Aucune logique métier ici — ce serveur est une **enveloppe de sécurité**, pas un agent.

## Outils exposés

### `lire(table, filtres, limite, ordre, appelant)`
- `table` : nom d'une des **16 tables autorisées**
- `filtres` : `{"colonne": valeur}` (égalité) — colonnes vérifiées contre la
  liste blanche de la table
- `limite` : max **1000** lignes (défaut 500) — les lectures se font **en batch**
- `ordre` : `"colonne"` ou `"colonne desc"` (colonne vérifiée)
- `appelant` : **obligatoire** — `RÉGISSEUR` · `INSPECTEUR` · `COMPAGNON` ·
  `JUGE` · `CONCIERGE` · `SENTINELLE` · `backend`

### `ecrire(table, lignes, si_doublon, appelant)`
- `lignes` : liste de dicts (colonne → valeur). Colonnes hors liste blanche = rejet.
- `si_doublon` : `"ignorer"` (défaut, idempotence N7 — `ON CONFLICT DO NOTHING`)
  ou `"mettre_a_jour"` (upsert sur la clé de la table — réservé à `run_logs`)
- Unicité par table (clé de conflit) : `tenders → reference`,
  `scores → (company_id, reference, algo_version)`, `run_logs → run_id`, etc.

## Périmètres par appelant (matrice v3.1)

| Appelant | Tables **lues** | Tables **écrites** |
|---|---|---|
| `RÉGISSEUR` | `run_logs` | `run_logs` |
| `INSPECTEUR` | `tenders` | `tenders` |
| `COMPAGNON` | `tenders`, `entreprises`, `feedback`, `verdicts`, `favoris` | `scores`, `digests` |
| `JUGE` | `tenders`, `entreprises`, `scores` | `verdicts` |
| `CONCIERGE` | `entreprises`, `utilisateurs`, `scores`, `verdicts`, `messages`, `digests`, `prospects` | `messages`, `feedback`, `digests`, `notifications` |
| `SENTINELLE` | `tenders` | `alertes_sentinelle` *(table P2 — non créée)* |
| `backend` | les 16 tables | les 16 tables |

Toute lecture/écriture hors périmètre = **rejet** (l'agent appelant doit le
convertir en alerte observabilité + ticket sécurité).

## Sécurité

- Liste blanche **stricte** : table, colonnes, opérateurs — rien de dynamique.
- Requêtes **paramétrées** (aucune concaténation de valeurs) — impossible
  d'injecter du SQL.
- Connexion **côté serveur** uniquement : `DATABASE_URL` dans `.env` (jamais commité).
- La connexion `postgres` (pooler) déjoue le RLS : la **vraie** barrière pour les
  agents est la liste blanche ci-dessus ; le RLS protège le **client** (navigateur).

## Démarrage

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt        # Windows
.venv/Scripts/python serveur.py                       # transport stdio
```

### Déclaration dans un client MCP (ex. Claude Desktop / LangGraph)

```json
{ "base-donnees": {
    "command": "python",
    "args": ["05-mcp-server/base-donnees/serveur.py"],
    "env": { "DATABASE_URL": "postgresql://..." } } }
```

## Tests

```bash
.venv/Scripts/python -m pytest tests/ -v
```
Les tests de sécurité tournent **sans base** ; le test « live » ne tourne que si
`DATABASE_URL` est défini (il vérifie un `lire` réel sur `run_logs`).
