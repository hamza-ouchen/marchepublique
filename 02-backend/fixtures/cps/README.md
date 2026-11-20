# 🧪 Fixtures CPS — documents synthétiques pour l'ingestion

> Emplacement : `02-backend/fixtures/cps/` · Migration associée : `migrations/005_cps.sql`
> Références : `11-documentation/v2.6/06-mission-midouni-cps.md` (production)
> et `11-documentation/v2.6/05-mission-ouchen-rag.md` (consommation RAG).
>
> ⚠️ **Aucune donnée réelle** : les PDF sont générés localement, le texte est
> entièrement fictif. Ne jamais déposer ici un PDF téléchargé depuis le portail.

---

## 1. À quoi servent ces fixtures

Elles permettent de tester **sans réseau et sans base** :

1. le découpage déterministe d'un CPS (`1.`, `2.1`, `2.2`… → sections citables) ;
2. le cas **multi-documents** d'un même AO (CPS + addenda) ;
3. la branche **OCR** (PDF sans couche texte) ;
4. la cohérence des statuts `tender_documents` (`extracted`, `echec`, `missing_cps`) ;
5. l'idempotence d'un rejeu (même référence + même document = une seule ligne).

Elles ne testent **pas** les embeddings ni Astra (responsabilité Ouchen) et ne
remplacent pas un test d'intégration réseau sur le portail.

---

## 2. Les quatre documents

| Cas | Référence (démo) | Document | Pages | Sections | Extraction |
|---|---|---|---|---|---|
| **A1** — CPS simple | `2026/DTR/0123` | `cps.pdf` | 2 | 7 | texte (pypdf) |
| **A2** — CPS principal | `2026/DTR/0124` | `cps.pdf` | 2 | 6 | texte (pypdf) |
| **A2** — addenda n° 1 | `2026/DTR/0124` | `addenda-1.pdf` | 1 | 3 | texte (pypdf) |
| **A3** — PDF scanné | `2026/DTR/0131` | `cps.pdf` | 1 | 0 | **OCR requis** (aucune couche texte) |

Les références correspondent aux lignes de démonstration de
`migrations/002_donnees_demo.sql` (table `tenders`), pour pouvoir insérer les
lignes `tender_documents` sans violer la clé étrangère.

---

## 3. Structure du dossier

```
02-backend/fixtures/cps/
├── README.md                  ← ce fichier
├── generer_fixtures.py        génère les PDF + les JSON attendus (zéro dépendance)
├── verifier_fixtures.py       vérifie PDF + cohérence des JSON
├── sources/                   vérité terrain (texte des documents)
│   ├── 2026-DTR-0123-cps.txt
│   ├── 2026-DTR-0124-cps.txt
│   ├── 2026-DTR-0124-addenda-1.txt
│   └── 2026-DTR-0131-cps.txt  (vérité OCR — absent du PDF généré)
├── pdfs/                      PDF synthétiques (générés, versionnés)
│   ├── 2026-DTR-0123/cps.pdf
│   ├── 2026-DTR-0124/cps.pdf
│   ├── 2026-DTR-0124/addenda-1.pdf
│   └── 2026-DTR-0131/cps.pdf
└── attendu/                   sections attendues, consommées par les tests
    ├── a1-0123-cps.json
    ├── a2-0124-cps.json
    ├── a2-0124-addenda-1.json
    └── a3-0131-cps.json
```

---

## 4. Regénérer et vérifier

```powershell
# Après modification d'une source : régénère PDF + JSON attendus
py -3.13 generer_fixtures.py

# Contrôle : PDF bien formés + JSON synchronisés avec les sources
py -3.13 verifier_fixtures.py
```

Le générateur n'utilise **aucune dépendance externe** (écriture PDF minimale
intégrée dans `generer_fixtures.py`). `pypdf` n'est nécessaire que pour la
production (Midouni) et les tests d'intégration.

---

## 5. Convention de découpage (celle que Midouni doit implémenter)

- Un titre est une ligne du type `1. Objet du marché`, `2.1 Terrassements…`,
  `4.2 Caution définitive` — numéro + espace + titre commençant par une majuscule.
- Une ligne comme `15 jours calendaires…` **n'est pas** un titre (minuscule).
- Une rubrique qui ne contient que des sous-rubriques (ex. `2. Consistance des
  travaux`) n'a pas de texte propre : elle **n'est pas insérée** (pas de section
  vide en base, `texte` est obligatoire).
- `section_no` = ordre de lecture (1..n) · `numero` = numéro d'origine (`2.1`)
  conservé pour la citation dans les verdicts.
- Les lignes avant le premier titre forment l'en-tête : elles ne sont pas
  stockées comme section.

Pour A3, le PDF ne contient **aucun opérateur de texte** : l'extraction renvoie
une chaîne vide → Midouni doit déclencher l'OCR, et ne jamais insérer de section
vide.

---

## 6. Exemple d'insertion (statut `extracted`)

```sql
-- A1 : un document + ses sections (sha256 = empreinte réelle du fichier)
with doc as (
  insert into tender_documents
    (reference, doc_type, filename, storage_path, sha256, size_bytes, pages,
     extraction, sections, char_count, statut)
  values
    ('2026/DTR/0123', 'CPS', 'cps.pdf', '2026/2026-DTR-0123/cps.pdf',
     '<sha256_du_fichier>', 3525, 2, 'pypdf', 7, 1534, 'extracted')
  returning id
)
insert into cps_sections (document_id, section_no, numero, titre, texte)
select id, 1, '1', 'Objet du marché',
       'Le présent cahier des prescriptions spéciales (CPS) définit les conditions…'
from doc
on conflict (document_id, section_no) do nothing;

-- A2 : deux documents pour le même AO (CPS + addenda) = deux lignes distinctes
insert into tender_documents
  (reference, doc_type, filename, storage_path, sha256, size_bytes, pages,
   extraction, sections, char_count, statut)
values
  ('2026/DTR/0124', 'CPS', 'cps.pdf',       '2026/2026-DTR-0124/cps.pdf',
   '<sha256_cps>', 3214, 2, 'pypdf', 6, 1379, 'extracted'),
  ('2026/DTR/0124', 'ADDITIF', 'addenda-1.pdf', '2026/2026-DTR-0124/addenda-1.pdf',
   '<sha256_addenda>', 1438, 1, 'pypdf', 3, 383, 'extracted')
on conflict (sha256) do nothing;
```

Le lien section → document se fait par `cps_sections.document_id` (retourné par
l'insertion, ou relu via `sha256`). Sur un rejeu, `sha256` étant **UNIQUE**,
`on conflict` évite le doublon ; pour récupérer quand même l'`id` existant :

```sql
insert into tender_documents (...) values (...)
on conflict (sha256) do update set updated_at = now()
returning id;
```

Après ingestion vectorielle, Ouchen passe la ligne à `ready` ; en cas d'échec
répété, il écrit `echec` **avec** `echec_raison` (contrainte SQL). Si aucun PDF
n'est trouvé sur la page de l'avis, Midouni écrit `missing_cps` avec le motif.

---

## 7. Règles

1. **Jamais de PDF réel** dans ce dossier — uniquement des documents synthétiques.
2. **Jamais de secret** (URL signée, token Storage, ICE) dans une fixture.
3. Le `.txt` de `sources/` est la **vérité terrain** ; les PDF et les JSON en
   découlent. Toute modification passe par `generer_fixtures.py` puis
   `verifier_fixtures.py`.
4. Les tests futurs (`tests/test_cps_ingest.py`) comparent l'extraction réelle
   aux `attendu/*.json` — toute divergence est un bug du découpage, pas un
   ajustement manuel du JSON.
