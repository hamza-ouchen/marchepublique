alter table public.tender_documents
  add column if not exists storage_bucket text not null default 'cps-originaux';

alter table public.tender_documents drop constraint if exists tender_documents_statut_check;
alter table public.tender_documents add constraint tender_documents_statut_check
  check (statut in ('downloading', 'extracted', 'ready', 'echec', 'missing_cps', 'stored'));
