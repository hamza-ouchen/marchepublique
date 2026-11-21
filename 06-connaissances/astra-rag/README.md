# SOUKNA — RAG de référence dans Astra DB

Responsable : Ouchen Hamza. Deux pipelines LangGraph inspirés de l'exemple CV, adaptés
à un corpus documentaire partagé :

**Livraison projet :** voir [RUNBOOK.md](../RUNBOOK.md) pour l'ingestion des CPS
depuis Supabase, les textes réglementaires validés, le raccordement MCP et les
vérifications de cette version. Les sections suivantes décrivent le socle PDF
de référence initial ; les corpus projet restent séparés de ce PDF.

```text
PDF → extraction paginée → Q/R + synthèses + glossaire → Astra → manifeste ready
question → validation → version publiée → recherche vectorielle → passages cités
```

Le socle PDF ne modifie ni les profils Supabase ni les verdicts du JUGE. Le worker
CPS ajoute uniquement la mise à jour des statuts documentaires et les journaux de
traitement ; l'adaptateur MCP est activé explicitement avec `MOTEUR=rag`.

## Source et séparation des responsabilités

Source fournie : `Base de Connaissances Officielle SOUKNA (RAG).pdf`, 34 pages,
125 blocs Q-001 à Q-125, tableaux initiaux et glossaire final. Le découpage produit
137 passages (125 Q/R, 6 fragments de synthèse, 6 fragments de glossaire).

Le modèle existant impose 512 tokens par entrée. Un premier essai a été refusé avant
toute insertion car un fragment dépassait cette limite. Le découpage final mesure
les tokens localement (tokenizer E5 parent embarqué, plafond conservateur 480) et
scinde sans troncature les blocs trop longs. Le PDF fourni atteint 336 tokens au
maximum par passage après ce traitement. Voir `TOKENIZER_NOTICE.md` pour la provenance
du tokenizer et la différence possible avec le prétraitement du service.

Empreinte SHA-256 :
`c7bc93a38546ea218e02d4a4a5680f4fb7e4cd14ae3b7c3373436727a6a1a06d`.

Le PDF reste à son emplacement local ; il n'est pas copié dans le dépôt public.
Les passages et rapports locaux sont dans `artifacts/`, ignoré par Git.

Ouchen fournit l'ingestion et la recherche. Mhalli peut exposer `service.chercher`
dans le serveur MCP `base-connaissances`. Aucun serveur MCP supplémentaire ni endpoint
HTTP n'est créé ici. Les noms de corpus `faq` / `reglementation` du contrat projet ne
sont pas assimilés silencieusement : ce PDF utilise `soukna_reference`.

## Installation reproductible

Python 3.12 ou supérieur. Python 3.12.12+ évite un avertissement de performance TLS du
client Astra observé avec les premières versions 3.12. Les dépendances complètes,
y compris les outils de test, sont verrouillées dans `requirements.lock`.

Depuis ce dossier :

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.lock
.venv\Scripts\python.exe -m pip check
```

Les commandes suivantes utilisent `python` de l'environnement activé. L'environnement
temporaire créé pour cette réalisation n'est pas une dépendance de déploiement.

## Configuration

Définir ces variables dans le processus serveur ou son gestionnaire de secrets :

| Variable | Usage |
|---|---|
| `ASTRA_DB_API_ENDPOINT` | Endpoint HTTPS Astra fourni par l'administrateur |
| `ASTRA_DB_API_TOKEN` | Jeton de service ; jamais dans le code ni dans un prompt |
| `ASTRA_DB_KEYSPACE` | Défaut `default_keyspace` |
| `ASTRA_DB_COLLECTION` | Défaut `sou9na` |

`.env.example` ne contient aucune valeur secrète. Ce module ne charge pas implicitement
un `.env`. `ASTRA_DB_CLIENT_ID` n'est pas requis par l'authentification Data API.
Le jeton transmis dans la conversation a été utilisé en mémoire du processus seulement ;
il doit être remplacé par l'administrateur puisqu'il a été partagé en clair.

La collection existante a été inspectée : vecteurs 1024 dimensions, similarité cosinus,
vectorize `nvidia/nv-embedqa-e5-v5`, index lexical activé. Le module utilise vectorize
tel que configuré, sans créer, modifier ou vider la collection. Aucun autre fournisseur
d'embeddings n'est substitué. La qualité FR/AR/darija de ce modèle reste à évaluer sur
un vrai jeu métier ; quelques tests de recherche ne constituent pas une certification.

## Préparation hors ligne

```powershell
python -m sou9na_rag prepare "CHEMIN\Base de Connaissances Officielle SOUKNA (RAG).pdf" --output artifacts/chunks.jsonl
```

Cette commande ne requiert ni accès réseau ni jeton. Elle vérifie la présence exacte
des 125 questions et conserve toutes les pages. Une page sans texte bloque le processus
au lieu de prétendre avoir effectué de l'OCR. Le glossaire est extrait par page et non
transformé en 35 objets prétendument structurés. Pour l'arabe des tableaux, les glyphes
extraits doivent être vérifiés sur le PDF original : aucune inversion de lettres ou
correction heuristique agressive n'est appliquée.

## Inspection et ingestion réelles

```powershell
python -m sou9na_rag inspect
python -m sou9na_rag ingest "CHEMIN\Base de Connaissances Officielle SOUKNA (RAG).pdf"
```

Les passages portent : empreinte du PDF, version de découpage, bloc Q, pages, texte,
catégorie, source déclarée et statut de validation juridique. `_id` est déterministe.
Une réexécution identique ignore les passages déjà présents. Une collision avec un
contenu différent échoue au lieu d'écraser une donnée. Les autres documents de `sou9na`
ne sont ni lus pour la recherche ni remplacés par ces insertions.

Le manifeste `ready` n'est inséré qu'après tous les passages. Une interruption laisse
éventuellement des fragments non publiés, exclus des recherches. Rejouer l'ingestion
permet de reprendre ; aucune suppression de nettoyage n'est automatique.

Une nouvelle édition du PDF crée une nouvelle empreinte et de nouveaux identifiants.
Si plusieurs éditions sont publiées, la recherche exige `--document-sha256` : elle ne
choisit pas arbitrairement une version et ne mélange pas les éditions.

## Recherche et contrat de sortie

```powershell
python -m sou9na_rag query "Quels sont les abonnements de SOUKNA ?" --top-k 5
python -m sou9na_rag query "Quels documents préparer ?" --document-sha256 EMPREINTE_SHA256
```

Intégration Python pour l'éditeur visuel ou MCP :

```python
from sou9na_rag.service import chercher

resultat = chercher("Que signifie un verdict À ÉTUDIER ?", corpus="soukna_reference")
```

Réponse : `status`, éventuellement `error`, `occurrences`, `passages`. Chaque passage
contient `texte`, `source` (nom du PDF), `source_id`, `document_sha256`, `bloc`, `pages`
(début/fin), `source_declaree`, `validation_juridique`, `score`.

États : `retrieved` (candidats retrouvés), `no_match` (aucun candidat), `invalid`
(requête invalide), `unavailable` (erreur backend/version non publiée/ambiguë).
Une panne n'est jamais présentée comme zéro résultat normal. Le nombre de passages et
la similarité ne sont pas une preuve de réponse suffisante. Il n'y a ni génération
de réponse finale, ni affirmation de confiance, ni décision GO/NO-GO dans ce module.
Les extraits ne sont pas tronqués arbitrairement à 400 caractères.

## Limites du corpus et garde-fous

Le titre « Officielle » est celui du fichier utilisateur ; il ne constitue pas une
validation par une autorité. Tous les passages portent `legal_validation=not_verified`.
Une source déclarée dans ce PDF n'est pas assimilée au texte officiel original.
Les citations renvoient au PDF, au numéro Q et aux pages. Les articles du décret ne
sont pas inventés ni considérés juridiquement vérifiés par l'import.

Le PDF décrit des agents HASSAD/MUTABIQ/RASSAIL et une heure de digest qui diffèrent
de l'organisation actuelle RÉGISSEUR/INSPECTEUR/JUGE/CONCIERGE et du planning du dépôt.
Il faut arbitrer ces écarts avant d'en faire la FAQ produit active. Le contenu stocké
n'altère jamais les règles d'exécution ni les autorisations des agents.

Le corpus est partagé et ne contient ici aucun dossier client ajouté par le module.
Il n'y a pas de support multi-tenant implicite : ne pas l'utiliser pour indexer des
pièces privées sans conception explicite des droits. Le jeton Astra reste côté serveur.

## Vérifications

```powershell
python -m ruff check .
python -m ruff format --check .
python -m pytest -q
python -m pip check
```

Les tests unitaires sont hors réseau et sans secrets. Ils couvrent notamment les
régressions du code CV (mots courts, requête invalide, texte vide), la conservation
des pages, les reprises idempotentes, les conflits d'identifiants, la non-publication
d'une ingestion partielle, la séparation des versions et des corpus.

Les résultats réellement obtenus sur le PDF et Astra seront consignés dans
`VERIFICATION.md`. Aucune CI GitHub n'est annoncée active à partir de ces tests locaux.
