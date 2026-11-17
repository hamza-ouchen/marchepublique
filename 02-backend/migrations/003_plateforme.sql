-- ═══════════════════════════════════════════════════════════════════
-- SOU9NA — Couche « plateforme » : utilisateurs, abonnements, OTP,
--          favoris, notifications, admins (à exécuter APRÈS 002)
-- Référence : README v2.4 (plans Découverte/Pro/Business, gestion
-- d'équipe plan 499, auth WhatsApp + OTP, favoris & statuts)
-- Idempotent : ON CONFLICT / IF NOT EXISTS (norme N7).
-- ═══════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────
-- 11. utilisateurs — les membres d'une entreprise (plan Business : plusieurs)
--     role 'admin' = gère l'équipe et le plan · role 'membre' = consultation
-- ─────────────────────────────────────────────────────────────────
create table if not exists utilisateurs (
  id            uuid primary key default gen_random_uuid(),
  company_id    text not null references entreprises(company_id) on delete cascade,
  auth_user_id  uuid,                         -- lien auth.users (OTP WhatsApp/email), nullable
  nom           text not null,
  email         text not null unique,
  whatsapp      text unique,
  role          text not null default 'membre' check (role in ('admin','membre')),
  statut        text not null default 'actif' check (statut in ('actif','invite','suspendu')),
  cree_le       timestamptz not null default now()
);
create index if not exists idx_utilisateurs_company on utilisateurs (company_id);

-- ─────────────────────────────────────────────────────────────────
-- 12. abonnements — plan de chaque entreprise
--     Découverte (0 DH) · Pro (199 DH) · Business (499 DH) · essai 14 jours
-- ─────────────────────────────────────────────────────────────────
create table if not exists abonnements (
  id          uuid primary key default gen_random_uuid(),
  company_id  text not null unique references entreprises(company_id) on delete cascade,
  plan        text not null check (plan in ('decouverte','pro','business')),
  statut      text not null check (statut in ('essai','actif','expire','resilie')),
  essai_fin   date,                           -- essai_debut + 14 jours
  prix_mad    numeric not null default 0 check (prix_mad in (0, 199, 499)),
  debute_le   date,
  termine_le  date,
  cree_le     timestamptz not null default now()
);

-- ─────────────────────────────────────────────────────────────────
-- 13. otp_codes — connexion par code à usage unique (WhatsApp / email)
-- ─────────────────────────────────────────────────────────────────
create table if not exists otp_codes (
  id           uuid primary key default gen_random_uuid(),
  canal        text not null check (canal in ('whatsapp','email')),
  destinataire text not null,
  code         text not null,
  expire_le    timestamptz not null,          -- ~10 minutes
  utilise_le   timestamptz,
  tentatives   int not null default 0,
  cree_le      timestamptz not null default now()
);
create index if not exists idx_otp_destinataire on otp_codes (destinataire, cree_le);

-- ─────────────────────────────────────────────────────────────────
-- 14. favoris — dossiers suivis par le client
--     statuts : à étudier · envoyé · gagné · perdu
-- ─────────────────────────────────────────────────────────────────
create table if not exists favoris (
  id             uuid primary key default gen_random_uuid(),
  company_id     text not null references entreprises(company_id) on delete cascade,
  user_id        uuid references utilisateurs(id) on delete set null,
  reference      text not null,
  statut_dossier text not null default 'a_etudier'
                 check (statut_dossier in ('a_etudier','envoye','gagne','perdu')),
  note           text,
  ajoute_le      timestamptz not null default now(),
  unique (company_id, reference)
);

-- ─────────────────────────────────────────────────────────────────
-- 15. notifications — la cloche du dashboard (digest, HITL, alertes)
-- ─────────────────────────────────────────────────────────────────
create table if not exists notifications (
  id         uuid primary key default gen_random_uuid(),
  company_id text not null references entreprises(company_id) on delete cascade,
  user_id    uuid references utilisateurs(id) on delete cascade,  -- null = toute l'équipe
  type       text not null default 'info' check (type in ('info','alerte','digest','hitl')),
  titre      text not null,
  contenu    text,
  lue        boolean not null default false,
  cree_le    timestamptz not null default now()
);
create index if not exists idx_notifications_company on notifications (company_id, lue);

-- ─────────────────────────────────────────────────────────────────
-- 16. admins — l'équipe Soukna interne (console /admin/waitlist, HITL, support)
--     Gouvernance collective : pas de chef de projet — tous « equipe ».
-- ─────────────────────────────────────────────────────────────────
create table if not exists admins (
  id       uuid primary key default gen_random_uuid(),
  nom      text not null,
  email    text not null unique,
  role     text not null default 'equipe' check (role in ('equipe','admin')),
  actif    boolean not null default true,
  cree_le  timestamptz not null default now()
);

-- ─────────────────────────────────────────────────────────────────
-- RLS — mêmes règles que le schéma principal : filtrage par company_id,
-- service_role (backend) déjoue le RLS, OTP/admins sans policy (internes).
-- ─────────────────────────────────────────────────────────────────
alter table utilisateurs  enable row level security;
alter table abonnements   enable row level security;
alter table favoris       enable row level security;
alter table notifications enable row level security;
alter table otp_codes     enable row level security;
alter table admins        enable row level security;

drop policy if exists client_ses_donnees on utilisateurs;
create policy client_ses_donnees on utilisateurs
  for select to authenticated using (company_id = public.mon_company_id());

drop policy if exists client_ses_donnees on abonnements;
create policy client_ses_donnees on abonnements
  for select to authenticated using (company_id = public.mon_company_id());

drop policy if exists client_ses_donnees on favoris;
create policy client_ses_donnees on favoris
  for select to authenticated using (company_id = public.mon_company_id());

drop policy if exists client_modifie_ses_favoris on favoris;
create policy client_modifie_ses_favoris on favoris
  for all to authenticated using (company_id = public.mon_company_id())
  with check (company_id = public.mon_company_id());

drop policy if exists client_ses_donnees on notifications;
create policy client_ses_donnees on notifications
  for select to authenticated using (company_id = public.mon_company_id());

-- otp_codes / admins : aucune policy → service_role uniquement.
