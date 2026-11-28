-- Traçabilité des requêtes et logs (concierge / pipeline), idempotente.
create table if not exists public.lg_requests (
  id uuid primary key default gen_random_uuid(),
  message_id text,
  sender_phone text,
  route text,
  outcome text,
  error text,
  started_at timestamptz not null default now(),
  finished_at timestamptz,
  latency_ms int,
  tokens_in int default 0,
  tokens_out int default 0,
  llm_cost_usd numeric(12, 6) default 0
);

create table if not exists public.lg_logs (
  id bigserial primary key,
  request_id uuid references public.lg_requests(id) on delete cascade,
  agent text not null,
  duration_s numeric(8, 3),
  detail text,
  created_at timestamptz not null default now()
);

create table if not exists public.lg_messages_seen (
  message_id text primary key,
  seen_at timestamptz not null default now()
);

create index if not exists idx_lg_requests_started on public.lg_requests (started_at);
create index if not exists idx_lg_logs_request on public.lg_logs (request_id);
