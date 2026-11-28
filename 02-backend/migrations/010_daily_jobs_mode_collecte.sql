-- Une seule collecte portail par lot : chaque job précise son mode et si
-- l'INSPECTEUR doit scraper (auto) ou réutiliser les avis déjà en base (none).
alter table public.daily_workflow_jobs
    add column if not exists mode text not null default 'auto';

alter table public.daily_workflow_jobs
    add column if not exists collecte text not null default 'auto';
