# Livraison RAG — Ouchen Hamza

## Périmètre et état réel

Cette livraison ajoute le worker CPS Supabase → Astra, les commandes d'ingestion
réglementaire, le raccordement au MCP existant et les tests de non-régression.
Elle conserve le moteur historique : le nouveau chemin s'active par `MOTEUR=rag`.
Les verdicts, profils clients, scores, canaux et migrations SQL ne sont pas modifiés.

Le schéma Supabase fourni le 20 novembre contient 18 tables et 178 colonnes.
Le traitement utilise `tender_documents.id` (bigint), `cps_sections.document_id`,
les états `extracted/ready/echec` et les colonnes existantes de `run_logs`.
Il ne crée pas de `cps_uploads` et ne rejoue aucune migration.

**Limites de validation :** aucune connexion Supabase d'exploitation n'est
configurée dans les dossiers accessibles. Le navigateur n'est pas accessible dans
cette session. L'autorisation de l'utilisateur ne remplace pas ces identifiants.
Les tests de cette livraison utilisent donc des adaptateurs simulés ; le parcours
MCP stdio est testé avec un vrai client, sans accès externe. L'ingestion antérieure
du PDF dans Astra est décrite dans `astra-rag/VERIFICATION.md` ; elle n'est pas une
preuve d'exécution du nouveau worker CPS sur les services réels.

Le corpus réglementaire demandé (décret, CCAG-T, procédures AO) reste à fournir et
valider. Le manifeste d'exemple est volontairement vide : la commande refuse de
publier un corpus vide, non approuvé ou dont l'empreinte a changé. Le PDF SOUKNA
n'est jamais reclassé comme texte réglementaire. Le jeu de 50 questions livré est
un jeu de recherche dérivé de ce PDF, **pas les 50 Q/A réglementaires indépendantes**
à approuver par l'équipe. Le score Recall@5 réel de ce jeu reste à mesurer.

## Installer

Depuis la racine du dépôt, avec Python 3.12.12 ou supérieur :

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r 05-mcp-server/base-connaissances/requirements-rag.lock
.venv\Scripts\python.exe -m pip install -r 06-connaissances/astra-rag/build-requirements.lock
.venv\Scripts\python.exe -m pip install --no-deps --no-build-isolation -e 06-connaissances/astra-rag
.venv\Scripts\python.exe -m pip check
```

Les locks couvrent les dépendances RAG/MCP et la construction du paquet. Ne pas
installer ces dépendances dans l'environnement personnel d'un autre service.

## Configurer les accès côté serveur

Variables nécessaires au processus, jamais au frontend ni au dépôt :

| Variable | Usage |
| --- | --- |
| `ASTRA_DB_API_ENDPOINT`, `ASTRA_DB_API_TOKEN` | Accès Astra existant |
| `ASTRA_DB_COLLECTION=sou9na` | Collection unique, aucun effacement ou recréation |
| `ASTRA_DB_KEYSPACE=default_keyspace` | Keyspace existant |
| `DATABASE_URL` | Connexion Postgres Supabase, TLS imposé, rôle serveur autorisé |
| `MOTEUR=rag` | Active le raccordement au package RAG dans le MCP |
| `MCP_TRANSPORT=streamable-http` | `/mcp` pour Agentic AI ; `stdio` pour client local |
| `MCP_AUTH_TOKEN` | Secret d'accès du MCP, requis pour toute exposition réseau |

Le worker lit uniquement l'environnement du processus : il ne charge pas `.env`.
Le serveur MCP conserve son chargeur `.env` historique. Ne pas activer `set -x`,
afficher les valeurs ou mettre un token dans une commande versionnée.

La collection existante utilise NVIDIA `nv-embedqa-e5-v5`, 1024 dimensions.
Le code vérifie cette configuration et refuse une autre configuration. Il utilise
`$vectorize` avec un budget local de 480 tokens, conforme à cette collection ; il
ne mélange pas des vecteurs Mistral et NVIDIA. **Aucune clé OpenRouter n'est requise.**
Le choix Mistral et les chunks de 800 tokens du document initial sont donc adaptés
à la collection réellement constatée, sans modification de celle-ci.

## Ingérer les CPS

Depuis la racine, après export sécurisé des variables :

```powershell
.venv\Scripts\python.exe 06-connaissances/ingestion/ingest-cps.py --document-id 2 --report 06-connaissances/astra-rag/artifacts/cps-2.json
# Ou un lot de documents extracted ; à lancer périodiquement par le scheduler existant :
.venv\Scripts\python.exe 06-connaissances/ingestion/ingest-cps.py --limit 100 --report 06-connaissances/astra-rag/artifacts/cps-lot.json
```

Le worker lit les sections dans leur ordre, sans retéléchargement ni OCR. Une
absence de sections produit un échec explicite à traiter avec Midouni. Les IDs
`cps:<document_id>:<section_no>:<seq>` sont stables. Un rejeu identique n'ajoute rien.
Une correction du texte extrait remplace les passages du même périmètre, avec
comparaison d'instantané ; elle ne peut pas écraser ceux d'une autre application.
Les anciens fragments devenus inutiles restent inertes, exclus par leur empreinte.

Un verrou transactionnel Postgres sérialise les workers par document. Les chunks
et leurs vecteurs sont relus avant publication du manifeste, puis le document est
passé à `ready`. Une panne d'indexation produit `echec` avec un motif sans secret.
Les erreurs réseau transitoires Astra sont retentées au plus trois fois ; une
donnée invalide n'est pas rejouée. Une panne de transaction Postgres laisse la
transaction annulée et impose de relancer la commande.

Les lectures ne servent que les documents `ready` dont le manifeste et le texte
Supabase ont la même empreinte. Une ingestion partielle ou une correction non
réindexée ne peut pas être mélangée à un autre état. Le retour de `echec` vers
`extracted` appartient au producteur/à l'opérateur, après correction de la cause.

## Ingérer les textes réglementaires

Ajouter les fichiers PDF/TXT/MD autorisés dans `corpus/` et un manifeste à côté.
Chaque entrée exige :

```json
{
  "documents": [{
    "source_id": "identifiant-stable",
    "file": "texte-valide.pdf",
    "sha256": "empreinte SHA-256 réelle du fichier",
    "source": "Titre exact de la source",
    "source_url": "URL officielle vérifiée",
    "rights": "Fondement autorisant son utilisation",
    "reviewed_by": "Membre ayant vérifié cette source",
    "validation": "approved"
  }]
}
```

```powershell
.venv\Scripts\python.exe 06-connaissances/ingestion/ingest-reglementation.py 06-connaissances/corpus/manifest.json --report 06-connaissances/astra-rag/artifacts/reglementation.json
```

La citation utilise la page et le fragment exacts. Aucun numéro d'article légal
n'est inventé à partir du numéro de chunk. Deux versions publiées d'une même source
bloquent la recherche : leur remplacement doit faire l'objet d'une décision de
l'équipe et d'une procédure d'archivage dédiée, sans suppression automatique.

## Raccorder Mhalli et Ayoub

Installer le package dans l'environnement qui exécute le serveur MCP, puis définir
`MOTEUR=rag`, les accès Astra et `DATABASE_URL`. Démarrer le serveur existant :

```powershell
cd 05-mcp-server/base-connaissances
..\..\.venv\Scripts\python.exe serveur.py
```

Conserver dans Agentic AI l'outil **chercher**, avec :

```json
{"requete": "caution provisoire", "corpus": "cps:2026/DTR/0123", "nombre": 5}
```

Les corpus supportés par ce MCP sont `faq`, `reglementation`, `cps:<reference>`.
`faq` est adapté explicitement au corpus `soukna_reference` du PDF ; la réglementation
n'y est jamais redirigée. Le résultat contient `passages`, `vide`,
`citation_imposee=true`, `hitl` et éventuellement `erreur`. Chaque passage conserve
texte, source, article/localisateur, score et les informations de page/document.
Maximum cinq passages, filtre strict par référence, aucun repli non filtré.

Le seuil technique de similarité vaut 0,75 ; il reste à calibrer sur le jeu validé.
Ce seuil n'est pas une preuve de pertinence. Les contenus non validés gardent
`hitl=true`, même si des passages existent. CONCIERGE doit conserver le refus poli
et la remontée humaine en cas de résultat vide, d'erreur ou de HITL. Il ne doit
jamais compléter une règle absente. Cette livraison n'invente pas une URL déployée :
l'hébergement et la configuration du flow restent à vérifier dans l'environnement
de l'équipe.

## Mesurer et surveiller

```powershell
cd 06-connaissances/astra-rag
python -m pytest -q
python -m ruff check .
python -m ruff format --check .
python evaluate_golden.py --dataset ../golden-set.json --report artifacts/golden-50.json
```

La dernière commande appelle les services réels et n'est pas exécutée par les tests
unitaires. Le rapport doit contenir 50 résultats, Recall@5 ≥ 0,8 et aucune erreur
backend pour être réussi. Il ne valide pas juridiquement le contenu du PDF.

Les ingestions CPS et réglementaires écrivent un résumé dans `run_logs` et un
rapport JSON détaillé dans le chemin `--report`. Le schéma actuel de `run_logs`
n'a pas de colonne source/rapport JSON/vector_dim : les détails restent donc dans
ce rapport (à archiver avec le même `run_id`), sans détourner les colonnes métier
`avis_nouveaux` ou `rejetes`. Une ingestion antérieure du PDF n'est pas rétroactivement
journalisée dans Supabase.

## Secrets, sauvegarde et livraison

Remplacer le jeton Astra exposé dans l'historique via le dashboard et le gestionnaire
de secrets de l'hébergement ; ne pas recopier ce jeton dans GitHub. Tester le nouveau
jeton, mettre à jour les services, puis révoquer l'ancien. Les secrets de production
ne sont pas nécessaires à la CI. Ne pas exposer le MCP HTTP sans authentification.

Le code ne crée ni sauvegarde ni rétention Astra : vérifier les possibilités et
la configuration de sauvegarde du compte auprès de l'administrateur. Les fichiers
source autorisés, leurs empreintes, les manifests et les rapports permettent de
reconstruire l'index. Éviter tout effacement global de la collection partagée.

La PR doit passer les contrôles RAG et la revue d'un autre membre. Un push ne vaut
ni validation du corpus, ni raccordement du flow, ni mise en production.
