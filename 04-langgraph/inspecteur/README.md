# 🔍 INSPECTEUR — collecte des documents d'offres (CPS/DCE)

Scrape le portail national `marchespublics.gov.ma`, **ne garde que les documents
pertinents pour les clients cibles (TPME)**, puis insère le texte et les sections
dans Supabase (`tender_documents`, `cps_sections`).

## Job complet (`--full-job`) — l'agent fait tout, dans l'ordre

```powershell
cd 04-langgraph
python -m inspecteur --full-job          # tout le cycle (idempotent)
python -m inspecteur --full-job --store-originals
```

Le cycle, dans l'ordre (chaque étape peut aussi s'exécuter seule) :

| Étape | Commande seule | Ce que ça fait |
|---|---|---|
| 1. Marche du listing | `--walk-only` | Reprise sur état persisté (`portal_walk_state.json`, cookies+pagestate) ; upsert idempotent des offres ; **les offres à deadline passée ne sont pas insérées** ; collecte brute `audit_map.jsonl` pour le ré-audit ; portail fermé ⇒ jamais « done » |
| 2. Statuts réels | `--status-only` | Deadline réelle depuis la page de détail ; **offres terminées supprimées** (scores/verdicts puis documents en cascade) |
| 3. Audit des absentes | `--audit-only` | Chaque référence mappée absente de la base est re-checkée live : ré-insertion automatique si réellement ouverte |
| 4. Documents | `--docs-only` | **Portail en source principale** : page détail → lien `DemandTelechargementDce` → formulaire (identité `DCE_*`) → `completeDownload` → ZIP → PDFs (ZIP imbriqués, dédoublonnés sha256, CPS d'abord) → ingestion **totale** (même texte insuffisant, qualité tracée) ; **aomaroc en repli uniquement** si le portail échoue |
| 5. Champs riches | `--fields-only` | `montant_mad`, `caution_mad`, `lots`, `qualifications_exigees`, `delai_jours` déduits du texte CPS/RC (regex FR déterministes, champs vides seulement) |

Réglages `.env` : `WALK_MINUTES`, `AUDIT_MINUTES`, `AUDIT_WORKERS`, `DOCS_MINUTES`,
`FIELDS_MINUTES`, `CPS_MAX_DOCS_PER_TENDER`, `AO_FALLBACK_ENABLED`, `DCE_*` (identité
déclarée au portail), `DELETE_FINISHED_OFFERS` (défaut : supprimées).

Planificateur local (exemple) — lance le job toutes les 30 min pendant les heures
d'ouverture du portail :

```powershell
schtasks /create /tn "InspecteurFullJob" /sc minute /mo 30 /st 07:30 /et 23:30 ^
  /tr "cmd /c cd /d <chemin>\marchepublique\04-langgraph && python -m inspecteur --full-job"
```

## Pourquoi une sélection

Le free tier Supabase Storage offre **500 Mo**. Stocker le PDF de chaque avis
(6 219 avis, souvent > 2 Mo) saturerait le bucket. La collecte est donc bornée
par : cible client · avis ouverts · taille/PDF · nombre de documents/run · budget
global · déduplication `sha256` · idempotence par référence.

## Cible (déduite des profils actifs)

- Secteurs et régions agrégés depuis `entreprises` (repli `companies`).
- Capacité max = `max(capacite_mad)` des profils actifs.
- Un avis est pertinent si : `statut` ouvert, `date_remise >= aujourd'hui`,
  secteur ∈ cible, région ∈ cible (si connue), `montant_mad <= capacité max`.
- Repli si aucun profil : 12 secteurs de référence + capacité 8 M MAD.
- Surcharge possible : `CPS_SECTORS`, `CPS_REGIONS`, `CPS_MAX_CAPACITY_MAD`.
- Source : portail national uniquement (`CPS_ALLOWED_HOSTS`, option `--allow-host`).
  Les sources externes protégées par JavaScript sont ignorées.

## Installation

```powershell
cd 04-langgraph
python -m pip install -r inspecteur/requirements.txt
# copier 04-langgraph/.env.example -> racine .env et renseigner DATABASE_URL,
# SUPABASE_URL, SUPABASE_SERVICE_KEY
```

## Commandes

```powershell
cd 04-langgraph

# 1) répétition (dry-run) : sélection + téléchargement, AUCUNE écriture
python -m inspecteur --dry-run --max-docs 5 --limit 50

# 2) réel : insertion en base (texte + sections), originaux NON uploadés
python -m inspecteur --max-docs 10 --limit 100

# 3) optionnel : uploader aussi les PDF dans 'cps-originaux'
python -m inspecteur --store-originals --max-docs 5
```

Sortie JSON : cible retenue, candidats, filtres (motifs), insérés, échecs, octets.

## Base de données

Migrations à appliquer dans Supabase (SQL Editor) :
`02-backend/migrations/005_cps.sql` (tables) et `006_storage_rls.sql` (bucket
privé + RLS). Le collecteur crée aussi les tables avec `CREATE TABLE IF NOT EXISTS`
au démarrage si les migrations n'ont pas été appliquées.

Le bucket `cps-originaux` reste à créer manuellement dans le Dashboard si
`--store-originals` est utilisé ; sans credentials, le mode dégradé continue
(texte en DB, original non stocké).

## OCR (PDF scannés)

Le portail publie des PDF image-only. L'extraction utilise `pypdf`, puis
`PyMuPDF` (rendu des pages) + `tesseract` en français :

```powershell
# Binaire : C:\Program Files\Tesseract-OCR\tesseract.exe (détecté automatiquement)
# Données fra : inspecteur/tessdata/fra.traineddata (non commité, .gitignore)
#   source : https://raw.githubusercontent.com/tesseract-ocr/tessdata/main/fra.traineddata
$env:TESSDATA_DIR = "04-langgraph\inspecteur\tessdata"
```

Sans `fra`, l'OCR replie sur `eng` ; sans binaire tesseract, le mode dégradé
conserve le résultat `pypdf` et marque le document `echec`.

## Tests (100 % hors-ligne)

```powershell
cd 04-langgraph
python -m pytest inspecteur/tests -q
```
