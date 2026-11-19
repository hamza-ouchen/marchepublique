# 📚 MCP `base-connaissances` — le RAG de Sou9na (outil `chercher`)

> Contrat **défini ensemble par Hamza Ouchen (contenu) et Hamza Mhalli
> (enveloppe MCP)** — README §9, jalons J5.
>
> Moteur **hybride** : corpus JSON locaux (`faq`, `reglementation`) puis
> Astra DB (collection unique `sou9na`) pour les CPS et en repli.
> Aucune exception ne remonte : une base vide est une réponse explicite.

## Contrat de l'outil (signé J5)

```
chercher(requete, corpus, nombre)
  → { "corpus": ..., "passages": [ { "texte", "source", "article", "score" } × 5 ] }
```

- **5 passages maximum** (défaut), triés par score décroissant.
- Chaque passage cite **sa source** (`source`) et son **article** —
  une réponse du CONCIERGE sans citation = rejet (règle transversale).
  Un passage sans citation est écarté du résultat (compteur `ignores`).
- Aucune donnée client ici : ce serveur ne connaît que le **corpus public**
  (réglementation, FAQ, CPS). Il ne lit jamais `scores` / `verdicts`.

Champs de réponse complémentaires :

| Champ | Sens |
|---|---|
| `vide` | `true` si aucun passage (base vide, corpus absent, aucun match) |
| `message` | explication en français quand `vide: true` |
| `erreur` | `corpus_invalide`, `requete_vide`, `astra_non_configure`, `astra_indisponible`, `moteur_indisponible` |
| `astra` | `{collection, documents, candidats}` — état de la base interrogée |
| `ignores` | passages écartés faute de citation |

## Corpora

| Corpus | Source | Contenu |
|---|---|---|
| `faq` | `corpus/faq.json` | FAQ générale (visiteur/client) — réponses citées |
| `reglementation` | `corpus/reglementation.json` | décret 2-22-431 (30 % TPME), CCAG, cautions, délais |
| `cps:<reference>` | Astra `sou9na` | sections de CPS ingérées par Ouchen (ex. `cps:2026/DTR/0123`) |

Format JSON local :

```json
{ "passages": [
  { "texte": "…", "source": "décret 2-22-431", "article": "art. 5" } ] }
```

Documents Astra : le moteur accepte les champs `texte|text|contenu`,
`source|document|filename` et `article|numero|titre`, et filtre par
`reference` ou `corpus` pour les corpus CPS.

## Qualité de recherche

- Insensible à la casse et aux accents (`décret` = `decret`).
- Pluriels et féminins rapprochés par racine (`cautions` ↔ `caution`,
  `plafonnees` ↔ `plafonnée`), sans rapprochement sous 4 lettres.
- Score **tf·idf** + **couverture** de la requête + **bonus d'expression
  exacte** ; tri déterministe (score puis ordre du corpus).
- `nombre` borné à **1..5**, même si l'appelant demande 50.

## Base vide (comportement garanti)

| Situation | Réponse |
|---|---|
| Fichier `corpus/*.json` absent | `vide: true`, message « corpus absent » |
| JSON illisible ou `passages: []` | `vide: true`, message « illisible / vide » |
| Collection Astra vide (0 document) | `vide: true`, `astra.documents: 0`, message « aucun document ingéré » |
| Astra sans credentials | `erreur: astra_non_configure`, `vide: true` |
| Astra en panne / timeout | `erreur: astra_indisponible`, `vide: true` |
| Aucun passage pertinent | `vide: true`, message « aucun passage ne correspond » |

## Démarrage

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt

# stdio (client local)
MCP_TRANSPORT=stdio .venv/Scripts/python serveur.py

# StreamableHTTP — POST http://<hôte>:8203/mcp
.venv/Scripts/python serveur.py
```

Le fichier `.env` local est chargé automatiquement **sans écraser** les
variables déjà définies. Variables (voir `.env.example`) :

| Variable | Rôle |
|---|---|
| `MOTEUR` | `auto` (défaut) : JSON local puis Astra · `lexical` : JSON seulement |
| `CORPUS_DIR` | dossier des corpus JSON (`corpus`) |
| `ASTRA_DB_API_ENDPOINT` / `ASTRA_DB_API_TOKEN` | Data API Astra |
| `ASTRA_DB_COLLECTION` / `ASTRA_DB_KEYSPACE` | `sou9na` / `default_keyspace` |
| `MCP_TRANSPORT` / `FASTMCP_HOST` / `FASTMCP_PORT` | transport et écoute HTTP |
| `MCP_AUTH_TOKEN` | Bearer attendu (sinon 401) — **même valeur que dans le client** |

## Tests

```bash
.venv/Scripts/python -m pytest tests/ -v
```

**19 tests**, zéro réseau : contrat J5, corpus absent/illisible/vide,
Astra vide ou en panne (simulée), bornes de `nombre`, citations
obligatoires, pluriels et accents.
