-- ═══════════════════════════════════════════════════════════════════
-- SOU9NA — Schéma v3 (10 tables) — Postgres / Supabase
-- Référence : README v2.4 §4.3 · matrice-acces-mcp-outils-bdd.md ·
--             doc colorée v3 (agents-es-matrice-cas-v3.pdf)
-- Exécution : Supabase → SQL Editor → coller le fichier → Run
-- Idempotent : sécurisé pour être réexécuté (CREATE IF NOT EXISTS).
-- ═══════════════════════════════════════════════════════════════════

create extension if not exists pgcrypto;

-- ─────────────────────────────────────────────────────────────────
-- 1. prospects — la file d'attente (landing « Demander un accès anticipé »)
--    Email obligatoire · WhatsApp facultatif · honeypot · consentement loi 09-08
-- ─────────────────────────────────────────────────────────────────
create table if not exists prospects (
  id                     uuid primary key default gen_random_uuid(),
  nom                    text not null,
  email                  text not null unique,
  whatsapp               text,                                   -- facultatif
  secteur                text not null,
  taille                 text,
  consentement_loi_09_08 boolean not null default false,
  honeypot               text default '',                        -- doit rester vide
  statut                 text not null default 'en_attente_approbation'
                         check (statut in ('en_attente_approbation','approuve','refuse')),
  cree_le                timestamptz not null default now()
);

-- ─────────────────────────────────────────────────────────────────
-- 2. invitations — lien d'activation unique, valable 7 jours, 2 canaux
-- ─────────────────────────────────────────────────────────────────
create table if not exists invitations (
  token        text primary key,               -- lien unique (usage unique)
  prospect_id  uuid references prospects(id),
  company_id   text,                           -- rempli à l'activation
  expire_le    timestamptz not null,           -- +7 jours, jamais 48 h
  utilise_le   timestamptz,                    -- null = non utilisé
  cree_le      timestamptz not null default now(),
  constraint invitation_expire_apres_creation check (expire_le > cree_le)
);

-- ─────────────────────────────────────────────────────────────────
-- 3. entreprises — profils (RLS par company_id)
--    Essai 14 jours dès confirmation · canaux opt-in · dashboard toujours alimenté
-- ─────────────────────────────────────────────────────────────────
create table if not exists entreprises (
  company_id      text primary key,            -- ICE (15 chiffres)
  user_id         uuid,                        -- lien auth.users (OTP WhatsApp), nullable
  nom             text not null,
  email           text not null unique,
  whatsapp        text,
  secteur         text not null,
  region          text not null,
  capacite_mad    numeric not null check (capacite_mad > 0),
  qualifications  text[] not null default '{}',
  historique      jsonb not null default '[]', -- [{annee, resultat, motif}]
  canaux_optin    jsonb not null default '{"whatsapp": true, "email": true}',
  essai_debut     date,                        -- essai 14 jours dès confirmation
  statut          text not null default 'actif'
                  check (statut in ('essai','actif','suspendu')),
  cree_le         timestamptz not null default now()
);

-- ─────────────────────────────────────────────────────────────────
-- 4. tenders — avis du portail (données publiques, écrites par INSPECTEUR)
--    statut : ouvert · clos · attribution (archives → SENTINELLE P2)
-- ─────────────────────────────────────────────────────────────────
create table if not exists tenders (
  reference              text primary key,
  organisme              text not null,
  objet                  text,
  secteur                text not null,
  region                 text not null,
  montant_mad            numeric not null check (montant_mad > 0),   -- plausibilité : positif
  caution_mad            numeric,
  lots                   text[] not null default '{}',
  qualifications_exigees text[] not null default '{}',
  delai_jours            int not null,
  date_publication       date,
  date_remise            date,
  date_collecte          date not null,
  statut                 text not null default 'ouvert'
                         check (statut in ('ouvert','clos','attribution')),
  source                 text not null default 'portail',            -- portail | secours | backfill
  source_url             text,
  cree_le                timestamptz not null default now(),
  mis_a_jour_le          timestamptz
);
create index if not exists idx_tenders_collecte on tenders (date_collecte);
create index if not exists idx_tenders_statut   on tenders (statut);

-- ─────────────────────────────────────────────────────────────────
-- 5. scores — Match /100 (COMPAGNON, déterministe, zéro LLM)
--    Pondérations validées : secteur 35 · région 20 · capacité 20 ·
--    qualifications 15 · historique 10
-- ─────────────────────────────────────────────────────────────────
create table if not exists scores (
  id            uuid primary key default gen_random_uuid(),
  company_id    text not null references entreprises(company_id),
  reference     text not null references tenders(reference),
  match_total   int not null check (match_total between 0 and 100),
  composantes   jsonb not null,               -- {secteur,region,capacite,qualifications,historique}
  points_perdus jsonb not null default '[]',
  algo_version  text not null,                -- ex. "1.0.0" — versionné
  calcule_le    timestamptz not null default now(),
  unique (company_id, reference, algo_version)
);
create index if not exists idx_scores_company on scores (company_id);
create index if not exists idx_scores_date    on scores (calcule_le);

-- ─────────────────────────────────────────────────────────────────
-- 6. verdicts — GO / À ÉTUDIER / NO-GO (JUGE) — Match ≠ verdict
-- ─────────────────────────────────────────────────────────────────
create table if not exists verdicts (
  id                 uuid primary key default gen_random_uuid(),
  company_id         text not null references entreprises(company_id),
  reference          text not null references tenders(reference),
  verdict            text not null check (verdict in ('GO','A_ETUDIER','NO_GO')),
  controles          jsonb not null,          -- {caution_vs_capacite, ice_attestations, qualifications, delai_atteignable}
  justifications     jsonb not null default '[]',  -- [{constat, reference}] — citation obligatoire
  risques_a_verifier jsonb not null default '[]',  -- ≥ 3 uniquement pour A_ETUDIER
  rendu_le           timestamptz not null default now(),
  unique (company_id, reference)
);

-- ─────────────────────────────────────────────────────────────────
-- 7. digests — contenu FR/AR écrit par COMPAGNON (7h30),
--    statut d'envoi écrit par CONCIERGE (distribution 8h00)
-- ─────────────────────────────────────────────────────────────────
create table if not exists digests (
  id            uuid primary key default gen_random_uuid(),
  company_id    text not null references entreprises(company_id),
  jour          date not null,
  contenu_fr    jsonb,
  contenu_ar    jsonb,
  bandeau       text,                          -- ex. « essai jour X sur 14 » · « service dégradé »
  statut_envoi  text not null default 'compose'
                check (statut_envoi in ('compose','envoye','echec')),
  envoye_le     timestamptz,
  unique (company_id, jour)
);

-- ─────────────────────────────────────────────────────────────────
-- 8. messages — conversations + journal d'envoi (CONCIERGE = unique émetteur)
--    company_id null = mode visiteur (landing), lié alors à prospect_id
-- ─────────────────────────────────────────────────────────────────
create table if not exists messages (
  id            uuid primary key default gen_random_uuid(),
  company_id    text references entreprises(company_id),
  prospect_id   uuid references prospects(id),
  canal         text not null check (canal in ('whatsapp','email','dashboard')),
  type          text not null default 'conversation' check (type in ('conversation','gabarit')),
  template      text,                          -- invitation | bienvenue | digest
  direction     text not null default 'entrant' check (direction in ('entrant','sortant')),
  texte         text,
  langue        text,                          -- fr | ar | darija
  intention     text,
  citation      jsonb,                         -- {document, article} — FAQ sans citation = rejet
  statut_envoi  text,                          -- envoye | echec-canal-ignore
  hitl          boolean not null default false,
  request_id    text,
  cree_le       timestamptz not null default now()
);
create index if not exists idx_messages_company on messages (company_id, cree_le);

-- ─────────────────────────────────────────────────────────────────
-- 9. feedback — gagné / perdu + motif (réinjecté dans l'historique du score)
-- ─────────────────────────────────────────────────────────────────
create table if not exists feedback (
  id         uuid primary key default gen_random_uuid(),
  company_id text not null references entreprises(company_id),
  reference  text not null,
  resultat   text not null check (resultat in ('gagne','perdu')),
  motif      text,
  date       date not null,
  unique (company_id, reference)
);

-- ─────────────────────────────────────────────────────────────────
-- 10. run_logs — chaque run : cron / manuel / backfill
-- ─────────────────────────────────────────────────────────────────
create table if not exists run_logs (
  id           uuid primary key default gen_random_uuid(),
  run_id       text not null unique,
  type         text not null check (type in ('cron','manuel','backfill')),
  statut       text not null,                  -- ouvert | cloture | echec
  debute_le    timestamptz not null default now(),
  cloture_le   timestamptz,
  avis_nouveaux int,
  rejetes      int,
  doublons     int,
  tokens       int,
  cout_mad     numeric
);

-- ─────────────────────────────────────────────────────────────────
-- RLS — les tables liées à un client sont filtrées par company_id.
-- Exceptions (internes, service_role uniquement) : prospects, invitations,
-- run_logs. tenders = données publiques (lecture seule pour tous).
-- NOTE : service_role déjoue le RLS — le backend (02-backend) l'utilise
-- toujours côté serveur, jamais côté navigateur.
-- ─────────────────────────────────────────────────────────────────

alter table entreprises enable row level security;
alter table tenders     enable row level security;
alter table scores      enable row level security;
alter table verdicts    enable row level security;
alter table digests     enable row level security;
alter table messages    enable row level security;
alter table feedback    enable row level security;
alter table prospects   enable row level security;
alter table invitations enable row level security;
alter table run_logs    enable row level security;

-- Helper : le client connecté (OTP WhatsApp → auth.users) → son company_id
create or replace function public.mon_company_id() returns text
language sql stable security definer as $$
  select company_id from public.entreprises where user_id = auth.uid() limit 1;
$$;

-- tenders : lecture publique (données officielles du portail)
drop policy if exists tenders_lecture_publique on tenders;
create policy tenders_lecture_publique on tenders
  for select to anon, authenticated using (true);

-- Placeholder client (à raffiner à l'intégration auth — dashboard) :
drop policy if exists client_ses_donnees on scores;
create policy client_ses_donnees on scores
  for select to authenticated using (company_id = public.mon_company_id());

drop policy if exists client_ses_donnees on verdicts;
create policy client_ses_donnees on verdicts
  for select to authenticated using (company_id = public.mon_company_id());

drop policy if exists client_ses_donnees on digests;
create policy client_ses_donnees on digests
  for select to authenticated using (company_id = public.mon_company_id());

drop policy if exists client_ses_donnees on feedback;
create policy client_ses_donnees on feedback
  for select to authenticated using (company_id = public.mon_company_id());

drop policy if exists client_ses_donnees on messages;
create policy client_ses_donnees on messages
  for select to authenticated using (company_id = public.mon_company_id());

-- prospects / invitations / run_logs : aucune policy → accès service_role uniquement.
