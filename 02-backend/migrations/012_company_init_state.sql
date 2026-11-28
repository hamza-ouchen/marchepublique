-- État d'initialisation d'une entreprise (premier remplissage en journée).
-- `ready` par défaut : les comptes historiques n'affichent pas d'écran d'attente.
alter table public.entreprises
  add column if not exists init_status text not null default 'ready',
  add column if not exists init_started_at timestamptz,
  add column if not exists init_error text;

alter table public.entreprises
  drop constraint if exists entreprises_init_status_check;
alter table public.entreprises
  add constraint entreprises_init_status_check
  check (init_status in ('ready', 'running', 'error'));
