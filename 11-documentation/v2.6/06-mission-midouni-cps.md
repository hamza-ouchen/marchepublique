# 🚜 Mission Hamza Midouni — Collecte des documents CPS

> 📌 **Qui fait quoi** : MIDOUNI (INSPECTEUR) détecte · télécharge · extrait · **conserve** ;
> OUCHEN vectorise et ingère ; MHALLI fait la charte MCP ; tout le monde ne touche
> que les **bases publiques** (portail + Supabase Storage).
>
> Références : `01-architecture-canaux.md` · `04-api-fastapi-concierge.md` ·
> `02-brief-ayoub-mcp-canaux.md` · matrice(MCP) v3 → v4 (prochain) ·
> Inspiration : projet Coach — `Knowledge_Ingest.json` + `ingest_books.py`

---

## 1. Contexte — votre périmètre élargi

Avant v2.6, ton périmètre = tenders + scores + verdicts en base. **NOUVEAU** :
chaque AO porte des **annexes (CPS)** — le PDF qui confirme:

- quelles questions de vérification (verdict) se poser avant de déposer un dossier ;
- quels sont les critères réels de qualification (RMA 2026, ISO 9001, etc.) ;
- quel est le barème éventuel ;
- quels sont les obstacles (cautions, assurances, délais).

> Sans ces documents, JUGE dit "À ÉTUDIER"… et reste "à étudier" éternellement.
> Avec eux : chaque verdict peut citer un article CPS **précis** → GO / NO-GO
> parfaitement défendable.

---

## 2. Ce que tu livres

| # | Livrable | Statut |
|---|---|---|
| L1 | Bucket `cps-originaux` en Supabase Storage + règles RLS | à faire |
| L2 | Référentiel documents : `tender_documents` + `cps_sections` (migrations `005` puis `006`) | **livrée** |
| L3 | Collecte automatique PDFs CPS dans cron (après INSPECTEUR collecte la liste) | à faire |
| L4 | Extraction déterministe (pypdf + OCR fallback) → `cps_sections` | à faire |
| L5 | `tender_documents.statut` remonte `extracted` → `ready` (via signal retour Ouchen) | à faire |
| L6 | Fixtures A1/A2/A3 (PDF synthétiques + JSON attendus) | **livrées** (`02-backend/fixtures/cps/`) |
| L7 | Endpoint `GET /tenders/{reference}/cps-status` (read-only) pour dashboard | à faire |

> ✅ **Réconciliation (19/11)** : `tender_documents` (déjà présente en base avec
> **1 CPS réel** — `GC4131483_additif.pdf`, OCR tesseract) est le **référentiel
> unique**. La migration `006_reconciliation_documents.sql` lui ajoute le
> workflow (`statut`, `echec_raison`, `sections`, `char_count`, `updated_at`),
> rattache `cps_sections` à son `id` et supprime `cps_uploads` (vide).

---

## 3. Pipeline (dans le graphe RÉGISSEUR)

```
6h00  POST /cron/run  (ou mode backfill)
  → RÉGISSEUR ouvre run_logs → INSPECTEUR (déjà existant)
  → INSPECTEUR : portalScraper.py → tenders (lignes ajoutées)
  → NOUVEAU : après chaque AO **nouvelle** (pas de doublon) :
        1) extrait lien(s) CPS du bloc avis (noms type « Cadre de réponse »,
           « Documents du marché », « Invitation »…)
        2) download PDF → bucket cps-originaux — chemin :
           <year>/<reference>/<num>_<name>.pdf  (ou /cps.pdf si 1 seul)
        3) extrait texte (pypdf) ; si < 100 caractères → OCR (pytesseract)
        4) divise par sections (regex titres numérotés « 1. » / « 2.1 »)
        5) écrit ou met à jour tender_documents
           (reference, doc_type='CPS', filename, storage_path, sha256,
            size_bytes, pages, extraction, extracted_text, source_url,
            statut='extracted', sections, char_count, downloaded_at)
        6) écrit cps_sections (document_id, section_no, numero, titre,
           texte, pages_section) — jamais de section vide
  → COMPAGNON (inchangé) → JUGE (inchangé) → CONCIERGE (inchangé)
  → Ouchen (déclenché par événement) : peut maintenant chercher/enrichir
```

### Politique "1 document = 1 écriture"

```text
avant ingestion d'un document :
    if tender_documents WHERE reference = <ref> AND filename = <nom>:
        continue          # idempotent : ne jamais réinscrire
    # filet de sécurité : sha256 est UNIQUE en base (même fichier = même ligne)
```

---

## 4. Schéma du référentiel (livré — `005_cps.sql` puis `006_reconciliation_documents.sql`)

```
table tender_documents (
  id               bigint generated always as identity primary key,
  reference        text not null references tenders(reference) on delete cascade,
  doc_type         text check (doc_type IN ('CPS','DCE','AVIS','ADDITIF','PV')),
  filename         text,                   ← cps.pdf · addenda-1.pdf · annexe-tech.pdf
  mime             text default 'application/pdf',
  storage_path     text not null,          ← "2026/2026-DTR-0123/cps.pdf" (bucket cps-originaux)
  sha256           text not null unique,   ← empreinte du fichier (déduplication)
  size_bytes       bigint,
  pages            int,
  extraction       text default 'pending', ← TECHNIQUE : pending · pypdf · ocr_tesseract_fra_best
  extracted_text   text,                   ← texte brut complet (avant découpage)
  source_url       text,
  request_id       text,
  downloaded_at    timestamptz default now(),
  -- ajoutés par 006 :
  statut           text not null default 'extracted'
                   check (statut IN ('downloading','extracted','ready','echec','missing_cps')),
  echec_raison     text,                   ← obligatoire si echec / missing_cps
  sections         int,                    ← nombre de lignes cps_sections
  char_count       int,                    ← longueur du texte extrait
  updated_at       timestamptz not null default now()
);

table cps_sections (
  id             uuid primary key default gen_random_uuid(),
  document_id    bigint not null references tender_documents(id) on delete cascade,
  section_no     int not null check (section_no > 0),   ← ordre de lecture 1..n
  numero         text,                                  ← numéro d'origine (« 2.1 », « ARTICLE 5 »)
  titre          text,
  texte          text not null check (length(trim(texte)) > 0),
  pages_section  text,                                  ← "p. 12-14"
  cree_le        timestamptz not null default now(),
  unique (document_id, section_no)
);
```

Points durs garantis par la base :

- **Pas de section vide** (`texte` non vide) ;
- **Pas d'échec muet** (`echec` / `missing_cps` exigent `echec_raison`) ;
- **Pas de doublon fichier** (`sha256` UNIQUE) : un rejeu met à jour au lieu d'insérer ;
- **Pas de section orpheline** (`document_id` NOT NULL + clé étrangère) ;
- **Suppression en cascade** : supprimer un document supprime ses sections.

`RLS` : aucune policy sur les deux tables → **service_role uniquement** (comme
`run_logs` ; `tender_documents` avait déjà RLS activé, sans policy). Ouchen lit
les sections pour les embeddings ; le frontend passe par FastAPI, qui ne renvoie
jamais le texte brut.

---

## 5. Règles (non négociables)

1. **Responsabilité de l'entrée** : le téléchargement commence après
   confirmation que le PDF est **public** — jamais de CPS secret/Restreinte ;
   si l'AO est fermé → skip propre.
2. **Taille limite** : un fichier PDF > 25 Mo ou > 200 pages → skip, log + alert.
3. **Pas de LLM** dans la chaîne de parsing — OCR simple seulement pour les
   pages scannées, sinon pypdf vaut pour tout.
4. **JAMAIS de copie locale persistante** — fichiers immédiatement uploadés
   dans Storage, ensuite supprimés (mémoire de parsing).
5. **Protection RLS** — `cps_sections` n'existe que pour le service (backend /
   Ouchen) ; le frontend n'a pas accès au texte brut.
6. **Idempotence** — 2 exécutions cron sur la même AO = 1 CPS ingéré.
7. **Multi-documents** — chaque AO peut avoir plusieurs documents (CPS principale
   + addenda + annexes). Un document = une ligne `tender_documents` identifiée
   par son `sha256` (unique) et nommée explicitement `cps.pdf`, `addenda-1.pdf`,
   `annexe-tech.pdf` — ne jamais réécrire un fichier sous un autre nom.

---

## 6. Collaboration

| avec | qui répond / dans quel sens |
|---|---|
| Ouchen (JUGE/RAG) | il lit tes `cps_sections` pour embeddings — consignes only after `statut='ready'`. **Ne jamais** lui demander de ré-télécharger pour tes propres tests — tu as sa référence de fixture. |
| Mhalli (RÉGISSEUR / MCP) | tu produis `tender_documents` + `cps_sections` ; Ouchen & Mhalli assument le `chercher()`. Ton code n'appelle pas MCP. |
| Ayoub (CONCIERGE) | pas de contact nécessaire au quotidien — seulement si Réponse rapide CPS est exposée au client (prudence : via `tenders/{ref}/info-public` stripped) |
| Outlit (observabilité) | chaque run CPS produit une trace LangSmith (`n_pdfs`, `taille`, `durée`, `exceptions`) remontée dans le run_logs quotidien |

---

## 7. Tests & DoD

**Tests** :
- Fixtures livrées : `02-backend/fixtures/cps/` (A1 = CPS simple 7 sections,
  A2 = CPS 6 sections + addenda 3 sections, A3 = PDF sans couche texte).
  `sources/` est la vérité terrain ; `attendu/*.json` porte les sections
  attendues ; `py verifier_fixtures.py` contrôle la cohérence.
- L'extraction réelle doit être comparée aux `attendu/*.json` — sans réseau,
  sans base, sans accès au portail (CI).
- Cas réels réseau : bouton "Collecte CPS" côté admin — limité à ton profil test.
- CPS absent (AO sans annexe) → `statut='missing_cps'` + motif — **pas** d'erreur.

**Définition du Ready**
- ✅ CPS ingéré pour A1 et A2 → `cps_sections` peuplée (7 / 6 + 3 sections)
- ✅ `tender_documents.statut='ready'` remontée (après embedding) pour A1 uniquement
- ✅ test de bout en bout : `chercher("caution provisoire", corpus="cps:2026/DTR/0123")`
  → au moins 1 passage **cité** (source + article)
- ✅ run cron en plein journée : INSPECTEUR collecte → CPS ingéré → digest
  contient le lien "Voir le Document CPS" (Ayoub l'expose dans le dashboard)

---

## 8. Ce que tu ne fais PAS

- ❌ Tu ne fais PAS d'appels Astra directement — OUCHEN uniquement
- ❌ Tu ne fais PAS d'appels Mistral/LLM du tout dans cette chaîne
- ❌ Tu ne retailles PAS les tenders existants — seulement doubler la collecte avec CPS
- ❌ Tu ne touches ni aux embeddings, ni au golden set, ni à `chercher()`
