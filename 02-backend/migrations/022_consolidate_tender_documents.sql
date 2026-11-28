-- Run with 02-backend/scripts/consolidate_tender_documents.py --finalize.
-- The runner supplies a bounded merge_scope and commits each batch separately.
ALTER TABLE public.tender_documents
    ADD COLUMN IF NOT EXISTS legacy_document jsonb,
    ADD COLUMN IF NOT EXISTS pre_merge_document jsonb;
ALTER TABLE public.cps_sections
    ADD COLUMN IF NOT EXISTS sujets text[] NOT NULL DEFAULT '{}',
    ADD COLUMN IF NOT EXISTS legacy_sections jsonb NOT NULL DEFAULT '[]';

ALTER TABLE public.cps_sections DISABLE TRIGGER cps_sections_sync_sections2;

-- MERGE BATCH

INSERT INTO public.tender_documents (
    reference, doc_type, filename, mime, storage_path, sha256, size_bytes,
    pages, extraction, extracted_text, source_url, request_id, downloaded_at,
    statut, echec_raison, sections, char_count, updated_at, storage_bucket, legacy_document
)
SELECT d.reference, d.doc_type, d.filename, d.mime, d.storage_path, d.sha256, d.size_bytes,
       d.pages, d.extraction, d.extracted_text, d.source_url, d.request_id, d.downloaded_at,
       d.statut, d.echec_raison, d.sections, d.char_count, d.updated_at,
       coalesce(d.storage_bucket, 'cps-originaux'), to_jsonb(d)
FROM public.tender_documents_duplicate d
JOIN merge_scope scope USING(reference)
ON CONFLICT (reference, sha256) DO UPDATE SET
    legacy_document = EXCLUDED.legacy_document
WHERE tender_documents.legacy_document IS DISTINCT FROM EXCLUDED.legacy_document;

-- Promote usable legacy text when the active document has no usable text.
UPDATE public.tender_documents d
SET pre_merge_document=to_jsonb(d)-'legacy_document'-'pre_merge_document',
    extracted_text=old.extracted_text, extraction=old.extraction, statut=old.statut,
    char_count=old.char_count, echec_raison=old.echec_raison, sections=old.sections,
    filename=coalesce(d.filename,old.filename), source_url=coalesce(d.source_url,old.source_url)
FROM public.tender_documents_duplicate old
WHERE (d.reference,d.sha256)=(old.reference,old.sha256)
  AND EXISTS (SELECT 1 FROM merge_scope scope WHERE scope.reference=old.reference)
  AND old.statut IN ('extracted','ready') AND length(trim(old.extracted_text))>0
  AND (d.statut NOT IN ('extracted','ready') OR nullif(trim(d.extracted_text),'') IS NULL);

CREATE TEMP TABLE merged_sections ON COMMIT DROP AS
SELECT s.document_id, s.section_no, s.numero, s.titre, s.texte, s.pages_section,
       NULL::timestamptz AS cree_le, s.sujets, 'cps_sections2'::text AS origin, to_jsonb(s)-'texte' AS payload
FROM public.cps_sections2 s
JOIN public.tender_documents d ON d.id=s.document_id
JOIN merge_scope scope USING(reference)
UNION ALL
SELECT d.id, s.section_no, s.numero, s.titre, s.texte, s.pages_section,
       s.cree_le, '{}'::text[], 'cps_sections_3', to_jsonb(s)-'texte'
FROM public.cps_sections_3 s
JOIN public.tender_documents_duplicate old ON old.id = s.document_id
JOIN merge_scope scope ON scope.reference=old.reference
JOIN public.tender_documents d ON (d.reference, d.sha256) = (old.reference, old.sha256);

CREATE INDEX ON merged_sections(document_id,section_no);
ANALYZE merged_sections;

-- Keep original numbering when free. Conflicting text remains a queryable
-- section with its original number and source recorded in legacy_sections.
WITH candidates AS (
    SELECT m.*, row_number() OVER (
        PARTITION BY m.document_id,m.section_no ORDER BY m.origin
    ) AS preference
    FROM merged_sections m
    WHERE m.section_no > 0 AND length(trim(m.texte)) > 0
      AND NOT EXISTS (SELECT 1 FROM public.cps_sections s
        WHERE s.document_id=m.document_id AND s.section_no=m.section_no)
)
INSERT INTO public.cps_sections (
    document_id, section_no, numero, titre, texte, pages_section, cree_le, sujets, legacy_sections
)
SELECT document_id, section_no, numero, titre, texte, pages_section, coalesce(cree_le,now()), sujets,
       jsonb_build_array(jsonb_build_object('origin',origin,'row',payload))
FROM candidates WHERE preference=1;

WITH existing AS (
    SELECT m.*, s.id
    FROM merged_sections m JOIN public.cps_sections s
      ON s.document_id=m.document_id AND s.section_no=m.section_no
     AND (s.numero,s.titre,s.texte,s.pages_section)
         IS NOT DISTINCT FROM (m.numero,m.titre,m.texte,m.pages_section)
), evidence AS (
    SELECT id, jsonb_agg(jsonb_build_object('origin',origin,'row',payload) ORDER BY origin) AS history,
           max(array_to_string(sujets,',')) FILTER (WHERE origin='cps_sections2') AS topics
    FROM existing GROUP BY id
)
UPDATE public.cps_sections s
SET legacy_sections=evidence.history, sujets=coalesce(string_to_array(evidence.topics,','),'{}')
FROM evidence WHERE s.id=evidence.id
  AND (s.legacy_sections,s.sujets) IS DISTINCT FROM
      (evidence.history,coalesce(string_to_array(evidence.topics,','),'{}'));

WITH pending AS (
    SELECT m.*
    FROM merged_sections m
    WHERE NOT EXISTS (SELECT 1 FROM public.cps_sections s
      WHERE s.document_id=m.document_id AND s.texte=m.texte
        AND s.legacy_sections @> jsonb_build_array(jsonb_build_object('origin',m.origin,'row',m.payload)))
), variants AS (
    SELECT document_id, section_no, numero, titre, texte, pages_section,
           min(cree_le) AS cree_le, max(array_to_string(sujets,',')) AS topics,
           jsonb_agg(jsonb_build_object('origin',origin,'row',payload) ORDER BY origin) AS history
    FROM pending GROUP BY document_id, section_no, numero, titre, texte, pages_section
), remaining AS (
    SELECT v.*,row_number() OVER (
      PARTITION BY document_id ORDER BY section_no,md5(texte),numero,titre,pages_section
    ) AS offset_no FROM variants v
), bounds AS (
    SELECT s.document_id,max(s.section_no) AS last_no
    FROM public.cps_sections s
    JOIN (SELECT DISTINCT document_id FROM remaining) target USING(document_id)
    GROUP BY s.document_id
)
INSERT INTO public.cps_sections (
    document_id, section_no, numero, titre, texte, pages_section, cree_le, sujets, legacy_sections
)
SELECT r.document_id,coalesce(b.last_no,0)+r.offset_no,r.numero,r.titre,r.texte,r.pages_section,
       coalesce(r.cree_le,now()),coalesce(string_to_array(r.topics,','),'{}'),r.history
FROM remaining r LEFT JOIN bounds b USING(document_id)
WHERE length(trim(r.texte))>0;

-- MERGE FINAL
LOCK TABLE public.tender_documents, public.tender_documents_duplicate,
    public.cps_sections, public.cps_sections2, public.cps_sections_3
    IN SHARE ROW EXCLUSIVE MODE;

CREATE FUNCTION public.sou9na_set_cps_topics() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.sujets := ARRAY(SELECT DISTINCT topic FROM unnest(
        NEW.sujets || public.soukna_cps_section_topics(concat_ws(' ',NEW.titre,NEW.texte))
    ) topic ORDER BY topic);
    RETURN NEW;
END;
$$;
CREATE TRIGGER cps_sections_set_topics BEFORE INSERT OR UPDATE OF titre, texte, sujets
ON public.cps_sections FOR EACH ROW EXECUTE FUNCTION public.sou9na_set_cps_topics();

-- Verify each source row against its preserved payload before removing any table.
CREATE TEMP TABLE verified_section_payloads ON COMMIT DROP AS
SELECT s.document_id, p->>'origin' AS origin, md5((p->'row')::text) AS fingerprint,
       md5(s.texte) AS text_fingerprint
FROM public.cps_sections s CROSS JOIN LATERAL jsonb_array_elements(s.legacy_sections) p;
CREATE INDEX ON verified_section_payloads(document_id,origin,fingerprint,text_fingerprint);
ANALYZE verified_section_payloads;

CREATE TEMP TABLE merged_sections ON COMMIT DROP AS
SELECT s.document_id,'cps_sections2'::text AS origin,to_jsonb(s)-'texte' AS payload,s.texte
FROM public.cps_sections2 s
UNION ALL
SELECT d.id,'cps_sections_3',to_jsonb(s)-'texte',s.texte
FROM public.cps_sections_3 s
JOIN public.tender_documents_duplicate old ON old.id=s.document_id
JOIN public.tender_documents d ON (d.reference,d.sha256)=(old.reference,old.sha256);
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM public.tender_documents_duplicate old
        LEFT JOIN public.tender_documents d ON (d.reference,d.sha256)=(old.reference,old.sha256)
        WHERE d.legacy_document IS DISTINCT FROM to_jsonb(old)
    ) OR EXISTS (
        SELECT 1 FROM merged_sections m LEFT JOIN verified_section_payloads v
          ON v.document_id=m.document_id AND v.origin=m.origin AND v.fingerprint=md5(m.payload::text)
         AND v.text_fingerprint=md5(m.texte)
        WHERE v.document_id IS NULL
    ) THEN
        RAISE EXCEPTION 'Consolidation incomplete; original tables must be retained';
    END IF;
END;
$$;

DROP TRIGGER cps_sections_sync_sections2 ON public.cps_sections;
DROP TABLE public.cps_sections2, public.cps_sections_3, public.tender_documents_duplicate;
