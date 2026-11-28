-- A document can be shared across tenders; new versions remain linked to their tender.
alter table public.tender_documents
    drop constraint if exists tender_documents_sha256_key;

create unique index if not exists tender_documents_reference_sha256_unique
    on public.tender_documents (reference, sha256);
