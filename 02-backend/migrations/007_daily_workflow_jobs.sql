-- Job quotidien durable, une exécution par entreprise et par date au Maroc.
create table public.daily_workflow_jobs (
    run_date date not null,
    company_id text not null references public.entreprises(company_id),
    state text not null default 'queued'
        check (state in ('queued', 'running', 'succeeded', 'failed')),
    queued_at timestamptz not null default now(),
    started_at timestamptz,
    finished_at timestamptz,
    exit_code integer,
    primary key (run_date, company_id)
);

-- Les jobs écrivent dans les mêmes fichiers de collecte INSPECTEUR.
create unique index daily_workflow_one_running
    on public.daily_workflow_jobs (state) where state = 'running';

alter table public.daily_workflow_jobs enable row level security;
