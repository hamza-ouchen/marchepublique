-- ═══════════════════════════════════════════════════════════════════
-- SOU9NA — Réconciliation des documents (à exécuter APRÈS 005)
--
-- DÉCISION (19/11) : `tender_documents` est le RÉFÉRENTIEL UNIQUE des
-- documents (CPS, DCE, avis, additifs, PV). Elle existait déjà dans
-- Supabase (créée hors migrations) et contient un CPS réel.
--
--   • `cps_uploads` (créée par 005, vide) est SUPPRIMÉE ;
--   • `cps_sections` est rattachée à `tender_documents.id` ;
--   • les champs de workflow (statut, motif, compteurs) sont ajoutés
--     à `tender_documents`.
--
-- Répartition : Midouni dépose la ligne `tender_documents` + les
-- sections ; Ouchen vectorise puis passe `statut = 'ready'`.
-- Idempotent : IF NOT EXISTS / DROP CONSTRAINT IF EXISTS (norme N7).
-- ═══════════════════════════════════════════════════════════════════

-- ─────────────────────────────────────────────────────────────────
-- 1. Workflow ajouté à tender_documents
--    `extraction` reste la TECHNIQUE (pending, pypdf, ocr_tesseract…)
--    `statut`     est l'ÉTAPE métier (downloading → extracted → ready)
-- ─────────────────────────────────────────────────────────────────
alter table tender_documents
  add column if not exists statut        text not null default 'extracted';
alter table tender_documents
  add column if not exists echec_raison  text;
alter table tender_documents
  add column if not exists sections      int;
alter table tender_documents
  add column if not exists char_count    int;
alter table tender_documents
  add column if not exists updated_at    timestamptz not null default now();

alter table tender_documents
  drop constraint if exists tender_documents_statut_check;
alter table tender_documents
  add constraint tender_documents_statut_check
  check (statut in ('downloading','extracted','ready','echec','missing_cps'));

alter table tender_documents
  drop constraint if exists tender_documents_motif_requis;
alter table tender_documents
  add constraint tender_documents_motif_requis
  check (
    statut not in ('echec','missing_cps')
    or (echec_raison is not null and length(trim(echec_raison)) > 0)
  );

alter table tender_documents
  drop constraint if exists tender_documents_sections_check;
alter table tender_documents
  add constraint tender_documents_sections_check
  check (sections is null or sections >= 0);

alter table tender_documents
  drop constraint if exists tender_documents_char_count_check;
alter table tender_documents
  add constraint tender_documents_char_count_check
  check (char_count is null or char_count >= 0);

create index if not exists idx_tender_documents_statut
  on tender_documents (statut, updated_at);
create index if not exists idx_tender_documents_reference
  on tender_documents (reference);

-- Reprise des lignes existantes : le texte déjà extrait donne la taille.
update tender_documents
   set char_count = length(extracted_text)
 where char_count is null and extracted_text is not null;

-- ─────────────────────────────────────────────────────────────────
-- 2. cps_sections → rattachée à tender_documents(id)
--    (table vide au moment de la migration : restructuration sans perte)
-- ─────────────────────────────────────────────────────────────────
alter table cps_sections drop constraint if exists cps_sections_document_fk;
alter table cps_sections drop constraint if exists cps_sections_pk;
drop index if exists idx_cps_sections_reference;

alter table cps_sections add column if not exists document_id bigint;
alter table cps_sections drop column if exists reference;
alter table cps_sections drop column if exists document_name;
alter table cps_sections alter column document_id set not null;

alter table cps_sections
  add constraint cps_sections_document_fk
  foreign key (document_id) references tender_documents(id) on delete cascade;

alter table cps_sections
  add constraint cps_sections_pk unique (document_id, section_no);

create index if not exists idx_cps_sections_document
  on cps_sections (document_id, section_no);

-- ─────────────────────────────────────────────────────────────────
-- 3. Suppression du doublon (vide) créé par 005
-- ─────────────────────────────────────────────────────────────────
drop table if exists cps_uploads;

-- ─────────────────────────────────────────────────────────────────
-- 4. Documentation en base
-- ─────────────────────────────────────────────────────────────────
comment on table tender_documents is
  'Référentiel UNIQUE des documents du portail (CPS/DCE/avis/additifs/PV) — Midouni dépose, Ouchen vectorise';
comment on column tender_documents.statut is
  'downloading → extracted (Midouni) → ready (Ouchen) | echec | missing_cps';
comment on column tender_documents.extraction is
  'Technique d''extraction : pending · pypdf · ocr_tesseract_fra_best…';
comment on column tender_documents.sections is
  'Nombre de sections écrites dans cps_sections';
comment on column tender_documents.char_count is
  'Nombre de caractères extraits (texte brut, avant découpage)';
comment on table cps_sections is
  'Sections numérotées d''un document — source des citations JUGE (service_role uniquement)';
comment on column cps_sections.document_id is
  'Référence tender_documents.id — le document parent porte reference/filename';
comment on column cps_sections.numero is
  'Numéro d''origine dans le document (« 2.1 », « ARTICLE 5 ») — utilisé dans les justifications';
