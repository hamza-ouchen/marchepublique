# 🧠 Mission Hamza Ouchen — Ingestion RAG (réglementation + CPS)

> 📌 **Qui fait quoi** : OUCHEN possède tout le **contenu** (documents, embeddings,
> corpus Astra) ; MIDOUNI produit ce qui entre dans Supabase (PDF, textes) ;
> MHALLI pose seulement le **cadre MCP** (`chercher`).
>
> Références : `01-architecture-canaux.md` · `04-api-fastapi-concierge.md` ·
> `02-brief-ayoub-mcp-canaux.md` · matrice(MCP) v3 → v4 (prochain)
> Inspiration : projet Coach — `Knowledge_Ingest.json` + `mcp-server/scripts/ingest_books.py`

---

## 1. Contexte — tes trois sources à ingérer

```
RÉGLEMENTATION (décret 2-22-431, CCAG, jurisprudence publiée)
      → corpus « reglementation » — référence obligatoire des verdicts

CPS DES APPELS D'OFFRES (extraites par Midouni — voir 06-mission-midouni-cps.md)
      → corpus « cps:<reference> » — citations par dossier

GOLDEN SET (50 Q/A — évaluations)
      → NON EMBARQUÉ — utilisé seulement pour mesurer le moteur
```

**Principe d'or** : chaque réponse produite doit porter des citations
(`source`, `article`, `page` → `passage{texte, source, article, score}`).
Une réponse sans citation est considérée comme fausse.

---

## 2. Compte Astra (déjà en main)

`05-mcp-server/base-connaissances/.env` (local, ignoré Git) contient :

```
ASTRA_DB_API_ENDPOINT  = https://…-us-east-2.apps.astra.datastax.com
ASTRA_DB_API_TOKEN     = AstraCS:…           ← ne jamais commiter
ASTRA_DB_CLIENT_ID     = DsPIdh…             ← idem
ASTRA_DB_COLLECTION    = sou9na              ← collection UNIQUE (tous les documents)
```

> ⚠️ Rotation : AstraCS:DsPIdh… est exposé dans le chat — **rotate en urgence**
> via le dashboard Astra quand tu as fini de tester.

**Décision collection (18/11)** : une **seule** collection `sou9na` contient
tous les types de documents (réglementation, CPS, FAQ, jurisprudence). Le
`corpus` de `chercher()` n'est qu'un **filtre logique** sur la métadonnée
`type` — jamais une collection physique séparée.

Modèle conseillé : `mistral-embed` (1024d) — une question = un vecteur ; programmé
localement pour le contrôle (débit + coût maîtrisés).

---

## 3. Pipeline A — corpus réglementaire (version Coach directe)

Script `06-connaissances/ingestion/ingest-reglementation.py` :

```text
pour chaque fichier .pdf/.txt/.md dans 06-connaissances/corpus/ :
    texte = extract_text(fichier)             # pypdf déterministe
    chunks = chunks_of(texte, 800, overlap=120)   # mots (pas LLM)
    vecteurs = mistral_client.embeddings.create(model="mistral-embed", inputs=chunks)
    collection = astra_client.collection("sou9na")
    for (i, chunk) : upsert({
        "_id": f"reg:{stem}:{i}",
        "type": "reglementation",
        "source": title, "article": i,
        "text": chunk, "$vector": vecteurs[i] })
    print(f"{title}: {len(chunks)} chunks ingérés")
```

Règles :
- **Pas de téléchargement** — fichiers versionnés dans le repo (libres/du domaine public)
- **Pas d'extraction LLM** — parsers déterministes uniquement
- **Authentification du doc** — chaque passage porte `source` + `article` + `chunk_index`
- **Déduplication** — skip si `_id` existe déjà (upsert idempotent)

Ce que tu livres : ce script, 3 fichiers de corpus (décret, CCAG-T, procédures AO),
le rapport d'exécution (nb de chunks, vectorisation, unicité).

---

## 4. Pipeline B — CPS d'une référence d'appel d'offres

> **Midouni les a déjà extraits** (PDF → Supabase Storage + `cps_sections`).
> Toi tu complètes l'injection vectorielle (oxygène du RAG).

Déclenchement : après que `tender_documents.statut = 'extracted'` (docs `doc_type='CPS'`, polling ou webhook) :

```text
1) Lire le document : tender_documents WHERE statut = 'extracted' AND doc_type = 'CPS'
        → d.id, d.reference, d.filename, d.pages
   puis cps_sections WHERE document_id = d.id ORDER BY section_no
        (ou pull le PDF depuis Storage si sections manquantes)
2) Construire chunks ≤ 800 tokens en conservant le numéro + titre de section
   métadonnées par chunk : {
     "type": "cps", "document_id": 2,
     "reference": "2026/DTR/0123", "filename": "cps.pdf", "section_no": 4,
     "numero": "4.1", "titre": "Caution provisoire",
     "source": "CPS — Commune de Sidi X", "page": 2 }
3) embeddings.create(model="mistral-embed", inputs=chunks)
4) collection.upsert(documents) — collection `sou9na`
   clé « cps:<document_id>:<section_no>:<seq> »
5) tender_documents.statut = 'ready'    (ou 'echec' après 3 retries, avec motif)
```

**Idempotence stricte** : `_id = "cps:<document_id>:<section_no>:<seq>"`. Une
même référence réingérée = upsert in-place — jamais de doublons. Le CPS et son
addenda cohabitent dans la **même** collection (documents distincts, donc
`document_id` différents) ; ils restent distinguables et citables séparément.

**Test avant mise en production** : fixtures livrées dans
`02-backend/fixtures/cps/` (A1 = CPS simple, A2 = CPS + addenda, A3 = PDF sans
couche texte). Ingérer A1 → `chercher("caution provisoire", corpus="cps:2026/DTR/0123")`
→ résultat **avec** citations (ou → échec explicite si embeddings KO).

---

## 5. Le `chercher` — contrat Confluence connaissance

Signature exposée par Ouchen+Mhalli (déjà dans le schéma MCP) :

```
chercher(requete, corpus, k=5)
  corpus = "reglementation" | "cps:<reference>"
  → { passages: [ { texte, source, article, score } × k ],
      citation_imposee: true }
```

`corpus` est un **filtre logique** appliqué à l'unique collection `sou9na`
(métadonnées `type` + `document_id` + `reference` + `filename`) — pas une
collection physique différente.

Toujours **max 5 passages** — jamais de résultats bruts sans citation ; si la
réponse n'existe pas dans le corpus → score 0.0 → refus poli (jamais inventé).

---

## 6. Golden set

`06-connaissances/golden-set.json` :

```json
{
  "questions": [
    { "ask": "Limite de la caution provisoire ?",
      "expected": "Plafond 15% du coût estimé — décret 2-22-431, art. 24",
      "corpus": "reglementation" }
  ]
}
```

**Utilisation** : test manuel ponctuel (`pytest test_golden.py`) avant le `deploy`,
jamais en ligne ; si un Q échoue → bug ingestion ou bug référence — jamais relâché en prod.
Objectif mesurable : **Recall@5 ≥ 80 %** sur les 50 questions.

---

## 7. Règles (non négociables)

1. **Pas de paraphrase personnelle** : ingérer uniquement les textes publics/libres
   ou ceux que l'équipe a le droit d'utiliser ; jamais une CPS couverte par copyright.
2. **Pas de données client** directement : les CPS publiques seulement.
3. **Pas d'appels LLM dans le pipeline** — parser déterministe + embeddings uniquement.
4. **Minimal metadata** : `type, document_id, reference, filename, source, numero, page, chunk_index` — jamais
   d'ICE, jamais de noms de personne, jamais de données non publiées.
5. **Contrat de qualité** : chaque ingestion se termine par un rapport
   (`nb_chunks`, `vector_dim`, `durée`, `source`) écrit dans `run_logs` — hors ce
   niveau, rien n'est "prêt" pour la production.

---

## 8. Ce avec quoi tu ne travailles pas directement

- ❌ Tu ne touches pas au bucket `cps-originaux` ni aux tables `tender_documents` /
  `cps_sections` *pour écrire* (lecture seule OK, sauf `statut` → `ready`/`echec`)
- ❌ Tu ne fais pas de fetch portail ni de PDF — c'est Midouni
- ❌ Tu n'appelles pas MCP `canaux` ni d'envoi mail — pas ton périmètre
- ❌ Tu n'écrits PAS dans `tenders/scores/verdicts`

---

## 9. Livrables

1. `ingest-reglementation.py` (3 fichiers) → exécution fumée + rapport
2. `ingest-cps.py` (CPS individuels) → test A1 → `chercher()` retourne 3 citations
3. `golden-set.json` (50 Q/A) + `test_golden.py`
4. Note d'ingestion (`RUNBOOK.md`) : lancer, monitoring, rotation_token
5. Brief Astra : index/backup répertoires, remplacement du token → plateforme secrets
