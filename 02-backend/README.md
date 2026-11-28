# API et workflow quotidien

Appliquer `migrations/007_daily_workflow_jobs.sql` et
`migrations/008_tender_document_versions.sql` après les migrations du
schéma existant. L'API et le worker doivent accéder à la même base PostgreSQL.

- Fournir `DATABASE_URL` aux deux processus.
- Fournir `CRON_SECRET` et `SOU9NA_CRON_COMPANY` à l'API. L'identifiant doit
  correspondre à une entreprise active dans la base.
- Fournir `SOU9NA_DASHBOARD_URL` (URL publique de la page du tableau de bord)
  au worker, ainsi que la configuration du serveur MCP canaux.
- Fournir `SUPABASE_URL` et `SUPABASE_SERVICE_ROLE_KEY` au worker pour les
  documents. Le bucket privé `cps-originaux` doit exister. Installer `pypdf`
  dans l'environnement du worker.
- Depuis `02-backend`, lancer `python -m uvicorn api:app` et
  `python daily_worker.py` comme deux services séparés.
- Configurer le planificateur externe pour envoyer `POST /cron/run` sur l'API
  HTTPS avec l'en-tête `X-Cron-Secret`. Utiliser le fuseau Africa/Casablanca.
  Désactiver l'ancienne tâche qui lance le batch Windows si elle vise la même base.

Le code HTTP 202 confirme l'enregistrement du job. Un second appel le même
jour pour la même entreprise renvoie le job existant, même s'il a échoué.
`GET /admin/scrape/status`, avec le même secret, expose le dernier état.
Les détails de chaque étape sont écrits dans les logs du worker.

Si le worker est interrompu pendant un job, l'état reste `running` et
bloque les autres jobs. Confirmer que le processus du workflow est arrêté et
vérifier les envois chez le fournisseur avant de marquer le job `failed` en
base. Le worker ne rejoue pas automatiquement une livraison interrompue.

Le job traite une seule entreprise. Il réutilise la collecte incrémentale
INSPECTEUR existante, fondée sur des mots-clés. Les alertes passent par
le serveur MCP canaux, qui doit être démarré séparément.

Après le calcul des scores du jour, INSPECTEUR parcourt jusqu'à 25 annonces
de l'entreprise, en donnant la priorité aux échéances proches. Il traite
les liens publics directs vers les PDF et les ZIP contenant des PDF.
Les originaux sont conservés dans Storage, et les sections et leurs pages
sont enregistrées dans PostgreSQL. Un téléchargement indisponible est
journalisé. Si les qualifications restent non vérifiées, JUGE conserve un
contrôle inconnu et peut citer une section utile pour la revue.
