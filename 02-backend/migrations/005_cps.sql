-- =====================================================================
-- Soukna — migration 005 : documents CPS (Cahier des Prescriptions
-- Spéciales) attachés aux tenders.
--
-- Aligné sur le schéma réel de Supabase (tender_documents + cps_sections).
-- Idempotent : ré-exécutable sans risque.
-- =====================================================================

create extension if not exists pgcrypto;

-- Documents bruts (PDF CPS/DCE/AVIS/...) attachés à un tender.
CREATE TABLE IF NOT EXISTS tender_documents (
    id            BIGSERIAL PRIMARY KEY,
    reference     TEXT NOT NULL REFERENCES tenders(reference) ON DELETE CASCADE,
    doc_type      TEXT CHECK (doc_type IN ('CPS','DCE','AVIS','ADDITIF','PV')),
    filename      TEXT,
    mime          TEXT,
    storage_path  TEXT NOT NULL,            -- ex. "2026/2026.DTR.0123/cps.pdf"
    sha256        TEXT NOT NULL UNIQUE,
    size_bytes    BIGINT,
    pages         INTEGER,
    extraction    TEXT,                     -- ex. "pypdf", "ocr_tesseract_fra_best"
    extracted_text TEXT,
    source_url    TEXT,
    request_id    TEXT,
    downloaded_at TIMESTAMPTZ,
    statut        TEXT NOT NULL CHECK (statut IN
                  ('downloading','extracted','ready','echec','missing_cps')),
    echec_raison  TEXT,
    sections      INTEGER CHECK (sections IS NULL OR sections >= 0),
    char_count    INTEGER CHECK (char_count IS NULL OR char_count >= 0),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- cohérence : echec/missing_cps exigent une raison
    CONSTRAINT tender_documents_motif_requis CHECK (
        statut NOT IN ('echec','missing_cps')
        OR (echec_raison IS NOT NULL AND length(trim(echec_raison)) > 0)
    )
);

CREATE INDEX IF NOT EXISTS idx_tender_documents_reference
    ON tender_documents(reference);
CREATE INDEX IF NOT EXISTS idx_tender_documents_statut
    ON tender_documents(statut);

-- Sections extraites d'un document (texte + titre + plage de pages).
CREATE TABLE IF NOT EXISTS cps_sections (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id  BIGINT NOT NULL REFERENCES tender_documents(id) ON DELETE CASCADE,
    section_no   INTEGER NOT NULL CHECK (section_no > 0),
    numero       TEXT,
    titre        TEXT,
    texte        TEXT NOT NULL CHECK (length(trim(texte)) > 0),
    pages_section TEXT,
    cree_le      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, section_no)
);

CREATE INDEX IF NOT EXISTS idx_cps_sections_document
    ON cps_sections(document_id);

-- Vue de commodité pour le dashboard (lecture seule, sans texte brut).
CREATE OR REPLACE VIEW v_tenders_documents AS
SELECT t.reference, t.organisme, t.objet, t.secteur, t.region,
       td.id AS document_id, td.doc_type, td.filename, td.mime,
       td.storage_path, td.sha256, td.size_bytes, td.pages, td.extraction,
       td.statut, td.echec_raison, td.sections, td.char_count,
       td.downloaded_at, td.updated_at, td.source_url
FROM tenders t
LEFT JOIN tender_documents td ON td.reference = t.reference;

-- RLS : service_role lit/écrit tout ; anon/authenticated n'ont aucun accès
-- au texte brut (cps_sections) ni aux documents.
ALTER TABLE tender_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE cps_sections ENABLE ROW LEVEL SECURITY;

-- Le backend (service_role) contourne RLS par défaut ; aucune policy pour
-- anon/authenticated = accès refusé (lecture via backend uniquement).