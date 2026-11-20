# Vérifications réalisées — 20 novembre 2026

Branche locale : `feature/hamza-ouchen/rag-astra`, créée depuis `origin/develop`
au commit `3d494dc35a83345154c490869ef1918f26f80a5e`.

Périmètre : uniquement `06-connaissances/astra-rag/`. Pas de modification de Supabase,
des workflows Agentic AI, des outils MCP de Mhalli ou des autres périmètres. Aucun
commit, push, PR ou déploiement de service n'a été réalisé. L'écriture dans Astra DB
est, elle, réelle et a été effectuée à la demande de l'utilisateur.

## Code et dépendances

| Commande / contrôle | Résultat réellement obtenu |
|---|---|
| `python -m pytest -q` | 25 tests réussis, hors réseau et sans clés |
| `python -m ruff check .` | Réussi |
| `python -m ruff format --check .` | 13 fichiers Python au format attendu |
| `python -m compileall -q sou9na_rag` | Réussi |
| `python -m pip check` | Aucun conflit de dépendances |
| `python -m pip wheel --no-deps --wheel-dir artifacts/wheels .` | Paquet final construit |
| Inspection du paquet | Fichier tokenizer embarqué présent |
| Recherche de motifs de secrets et de dépendances locales dans les sources | Aucun jeton Astra/GitHub détecté ; aucun chemin de dépendance locale dans le lock |

L'environnement de test utilise Python 3.12. Le client Astra signale un avertissement
de performance TLS sur les versions Python 3.12 antérieures à 3.12.12 ; les tests et
opérations ci-dessous ont néanmoins réussi. `requirements.lock` fige les versions
installées. Ce contrôle local ne constitue pas une CI GitHub active.

## Préparation documentaire

Commande : `python -m sou9na_rag prepare "CHEMIN_PDF" --output artifacts/chunks.jsonl`.

- PDF : 34 pages ; empreinte SHA-256
  `c7bc93a38546ea218e02d4a4a5680f4fb7e4cd14ae3b7c3373436727a6a1a06d`.
- 125 questions uniques, sans identifiant manquant ou dupliqué.
- 137 passages : 125 Q/R, 6 fragments de synthèse, 6 fragments de glossaire.
- Couverture des 34 pages ; aucune troncature du texte en fin de document.
- Version finale de découpage : `qa-pages-e5-v2`.
- Maximum mesuré : 336 tokens locaux par passage, sous le plafond conservateur de 480.
- Une page de glossaire a été comparée visuellement au PDF original. Cela ne certifie
  pas la restitution parfaite de tous les caractères arabes dans les tableaux.

Un premier essai avec des blocs limités uniquement en caractères a été refusé par
NVIDIA (512 tokens maximum), avant toute insertion. Il a motivé le découpage mesuré
en tokens et les tests de non-troncature. Une interruption API ultérieure a laissé
des passages partiels non publiés ; la reprise a conservé ces passages sans doublon.

## Astra DB — opérations réelles

Collection existante `sou9na`, keyspace `default_keyspace` ; configuration conservée :
vectorize NVIDIA `nvidia/nv-embedqa-e5-v5`, dimension 1024, cosinus, lexical activé.
Le module utilise la recherche vectorielle ; il ne prétend pas exécuter une recherche
hybride simplement parce que l'index lexical existe.

Commande d'ingestion : `python -m sou9na_rag ingest "CHEMIN_PDF"`.

- Reprise finale : état `ready`, 112 nouvelles insertions et 25 passages reconnus.
- Manifeste publié après la fin complète de l'import.
- Seconde ingestion complète : état `ready`, 0 insertion, 137 passages reconnus.
- Lecture finale : ensemble des 137 identifiants identique aux passages préparés.
- 125 identifiants de questions distincts retrouvés dans Astra.
- Un vecteur enregistré relu : 1024 dimensions.
- Date de publication du manifeste : `2026-11-20T09:09:05.369933+00:00`.
- La réutilisation du manifeste conserve sa date réelle de création.
- Aucune collection recréée ou vidée ; aucune suppression effectuée.

Les rapports bruts non secrets sont conservés localement dans `artifacts/`, ignoré
par Git : `ingest-report.json`, `reingest-report.json`,
`final-astra-verification.json` et `live-search-report.json`.

## Recherche réelle

Commande : `python evaluate_live.py`, avec les six questions de
`evaluations/smoke_questions.json`.

| Sujet de la question | Bloc attendu | Rang obtenu |
|---|---|---|
| Définition de SOUKNA | Q-001 | 1 |
| Signification des verdicts | Q-007 | 1 |
| Langues supportées | Q-012 | 1 |
| Dépôt d'offre par SOUKNA | Q-016 | 1 |
| Constitution du cautionnement | Q-061 | 1 |
| Délai de paiement | Q-097 | 1 |

Les six recherches ont retourné la source, le bloc, les pages et l'empreinte du PDF.
Ces essais FR proches des formulations du document sont un contrôle de bon
fonctionnement, pas un golden set indépendant ni une mesure générale de précision.
Aucune réponse juridique générée ni validation réglementaire n'a été effectuée.

## Limites et étape humaine suivante

Tous les passages restent `legal_validation=not_verified`. Arbitrer les écarts de
noms d'agents et de planning entre le PDF et le projet actuel avant diffusion client.
Évaluer séparément les questions inédites, l'arabe et la darija. Mhalli peut exposer
`sou9na_rag.service.chercher` via le serveur MCP existant après revue du contrat de
sortie et des noms de corpus. Une revue indépendante est requise avant intégration.

Le jeton partagé dans la conversation n'est présent dans aucun fichier source ; il
a été fourni uniquement à l'environnement des processus d'accès Astra. Le responsable
doit le renouveler et mettre la nouvelle valeur dans le gestionnaire de secrets du
service, sans la transmettre dans un prompt.
