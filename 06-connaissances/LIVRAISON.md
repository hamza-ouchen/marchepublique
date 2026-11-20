# État de livraison RAG — 20 novembre 2026

Branche de livraison : `feature/hamza-ouchen/rag-livraison`, créée depuis
`origin/develop` (`a71e9a7`). Le regroupement expérimental des autres branches
reste dans son dossier initial ; cette branche ne le publie pas.

## Livré en code

- Socle LangGraph d'ingestion/recherche du PDF SOUKNA avec tokenizer embarqué.
- Worker CPS lisant le schéma Supabase fourni : sections, documents, états et logs.
- Upserts CPS idempotents, contrôle des vecteurs, publication par instantané,
  mise à jour transactionnelle de `ready/echec` et séparation stricte par référence.
- Ingestion PDF/TXT/MD réglementaire avec manifeste de provenance, droits et revue.
- Adaptateur opt-in `MOTEUR=rag` dans le serveur MCP existant, sans modifier son
  protocole d'appel ni le comportement par défaut du moteur historique.
- Jeu de non-régression de 50 questions du PDF, évaluateur Recall@5 et runbook.
- Workflow GitHub Actions pour les tests RAG/MCP, les fixtures et le paquet Python.

## Vérifications locales

Les commandes et leurs limites sont consignées dans le runbook. Les premiers
contrôles donnent 59 tests RAG et 22 tests MCP réussis, dont un échange MCP stdio
réel avec le package et un refus explicite sans accès backend. Le lint RAG et la
construction de la wheel réussissent. La wheel contient le tokenizer nécessaire.

L'installation des locks dans l'environnement de vérification existant et son
`pip check` réussissent. Une tentative d'installation dans un second environnement
vierge a été interrompue par un manque d'espace disque ; cet environnement
temporaire a été supprimé. La CI doit confirmer l'installation dans un environnement
Linux vierge ; son résultat ne doit pas être supposé à partir des tests locaux.

Ces résultats ne sont pas des tests de connexion aux services Supabase et Astra
d'exploitation. Le schéma SQL est testé par des adaptateurs ; il n'a pas été
exécuté contre une base Postgres locale (Docker n'est pas démarré).

## Acceptation complète encore à obtenir

1. Configurer les accès serveur Supabase/Astra à jour et lancer le worker sur un
   document CPS réel déjà extrait, puis vérifier `run_logs` et une recherche citée.
2. Fournir et approuver les trois textes réglementaires demandés. Le manifeste
   reste vide tant que ces sources ne sont pas validées ; aucune règle n'est inventée.
3. Approuver le jeu indépendant de 50 Q/A réglementaires. Le jeu PDF livré est
   distinct ; son Recall@5 réel doit encore être exécuté, pas supposé réussi.
4. Avec Mhalli et Ayoub, configurer `MOTEUR=rag` sur le MCP installé et vérifier
   l'appel depuis CONCIERGE avec les citations et le chemin HITL.
5. Faire la revue indépendante de la PR et examiner le résultat réel de sa CI.

Le code est soumis pour revue avec ces limites. Il ne s'agit pas d'une déclaration
de mission acceptée à 100 %, d'une modification de la base réelle ou d'un déploiement.
