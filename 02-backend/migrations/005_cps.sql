-- ═══════════════════════════════════════════════════════════════════
-- SOU9NA — Couche « documents CPS » (2 tables, à exécuter APRÈS 004)
-- Référence : 11-documentation/v2.6/06-mission-midouni-cps.md
--             + 11-documentation/v2.6/05-mission-ouchen-rag.md
-- Exécution : Supabase → SQL Editor → coller le fichier → Run
-- Idempotent : CREATE TABLE/INDEX IF NOT EXISTS + contraintes nommées (norme N7).
--
-- DÉCISION ASTRA (18/11) — UNE SEULE collection `sou9na` pour TOUS les
-- documents (réglementation, CPS, FAQ, jurisprudence). Le `corpus` passé à
-- `chercher()` reste un FILTRE LOGIQUE (métadonnée `type`), jamais une
-- collection physique séparée.
--
-- ⚠️ RÉCONCILIÉE PAR 006 (19/11) : `cps_uploads` est supprimée ; le
-- référentiel unique est `tender_documents` (existante, contient un CPS réel).
-- `cps_sections` est rattachée à `tender_documents.id`. Ce fichier reste
-- l'historique de la première version de la couche CPS.
--
-- Flux des statuts (une seule vérité, deux propriétaires) :
--   downloading ──(Midouni)──> extracted ──(Ouchen)──> ready
--        │                         │
--        └──> echec / missing_cps <┘  (motif obligatoire, jamais silencieux)
-- ═══════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────
-- 17. cps_uploads — un PDF déposé dans Supabase Storage (bucket
--     `cps-originaux`), avec son état de traitement.
--     Un AO peut porter PLUSIEURS documents : CPS principale + addenda
--     + annexes → clé métier (reference, document_name).
-- ─────────────────────────────────────────────────────────────────
create table if not exists cps_uploads (
  id               uuid primary key default gen_random_uuid(),
  reference        text not null references tenders(reference) on delete cascade,
  document_name    text not null,              -- cps.pdf · addenda-1.pdf · annexe-tech.pdf
  storage_path     text,                       -- 2026/2026-DTR-0123/cps.pdf (bucket cps-originaux)
  checksum_sha256  text,                       -- empreinte du fichier (rejeu / doublons)
  pages            int     check (pages is null or pages > 0),
  sections         int     check (sections is null or sections >= 0),
  char_count       int     check (char_count is null or char_count >= 0),
  taille_octets    bigint  check (taille_octets is null or taille_octets > 0),
  statut           text not null default 'downloading'
                   check (statut in ('downloading','extracted','ready','echec','missing_cps')),
  echec_raison     text,                       -- obligatoire si echec / missing_cps
  downloaded_at    timestamptz not null default now(),
  updated_at       timestamptz not null default now(),

  constraint cps_uploads_reference_document_unique unique (reference, document_name),
  constraint cps_uploads_storage_path_unique      unique (storage_path),

  -- Un PDF téléchargé a toujours un chemin ; seul `missing_cps` en est dispensé.
  constraint cps_uploads_chemin_requis check (
    statut in ('downloading','missing_cps') or storage_path is not null
  ),

  -- Tout blocage doit être expliqué (pas d'échec muet).
  constraint cps_uploads_motif_requis check (
    statut not in ('echec','missing_cps')
    or (echec_raison is not null and length(trim(echec_raison)) > 0)
  )
);

create index if not exists idx_cps_uploads_reference on cps_uploads (reference);
create index if not exists idx_cps_uploads_file    on cps_uploads (statut, updated_at);
create index if not exists idx_cps_uploads_checksum on cps_uploads (checksum_sha256);

-- ─────────────────────────────────────────────────────────────────
-- 18. cps_sections — découpage déterministe du texte du PDF.
--     `section_no` = ordre de lecture (1..n) · `numero` = numéro
--     d'origine (« 2.1 », « ARTICLE 5 ») pour la citation.
-- ─────────────────────────────────────────────────────────────────
create table if not exists cps_sections (
  id             uuid primary key default gen_random_uuid(),
  reference      text not null,
  document_name  text not null,
  section_no     int  not null check (section_no > 0),
  numero         text,                         -- numéro d'origine (citation)
  titre          text,
  texte          text not null check (length(trim(texte)) > 0),
  pages_section  text,                         -- « p. 12-14 »
  cree_le        timestamptz not null default now(),

  constraint cps_sections_pk unique (reference, document_name, section_no),
  constraint cps_sections_document_fk
    foreign key (reference, document_name)
    references cps_uploads (reference, document_name) on delete cascade
);

create index if not exists idx_cps_sections_reference on cps_sections (reference, document_name, section_no);

-- Recherche lexicale de secours (avant/à côté des vecteurs Astra).
create index if not exists idx_cps_sections_fts
  on cps_sections
  using gin (to_tsvector('french',
    coalesce(numero, '') || ' ' || coalesce(titre, '') || ' ' || texte));

-- ─────────────────────────────────────────────────────────────────
-- RLS — tables internes : aucune policy → service_role uniquement
-- (comme run_logs / otp_codes / admins). Le frontend ne voit jamais
-- le texte brut ; l'état CPS est exposé par FastAPI, filtré.
-- ─────────────────────────────────────────────────────────────────
alter table cps_uploads  enable row level security;
alter table cps_sections enable row level security;

comment on table cps_uploads is
  'PDF CPS déposés dans Storage (bucket cps-originaux) + état downloading/extracted/ready/echec/missing_cps';
comment on column cps_uploads.statut is
  'downloading → extracted (Midouni) → ready (Ouchen) | echec | missing_cps';
comment on table cps_sections is
  'Sections numérotées extraites des CPS — source des citations JUGE (texte brut, service_role uniquement)';
comment on column cps_sections.numero is
  'Numéro d''origine dans le document (« 2.1 », « ARTICLE 5 ») — utilisé dans les justifications';
