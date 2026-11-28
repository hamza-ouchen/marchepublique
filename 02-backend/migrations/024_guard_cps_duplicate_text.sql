CREATE OR REPLACE FUNCTION public.sou9na_merge_repeated_cps_text()
RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE
    keeper uuid;
    incoming jsonb;
BEGIN
    NEW.sujets := ARRAY(
        SELECT DISTINCT topic FROM unnest(
            NEW.sujets || public.soukna_cps_section_topics(concat_ws(' ',NEW.titre,NEW.texte))
        ) AS topic ORDER BY topic
    );
    PERFORM pg_advisory_xact_lock(hashtext('sou9na:cps_sections'), hashtext(NEW.document_id::text));

    SELECT s.id INTO keeper FROM public.cps_sections s
    WHERE s.document_id=NEW.document_id AND s.texte=NEW.texte
    ORDER BY s.section_no,s.id LIMIT 1;
    IF keeper IS NULL THEN
        RETURN NEW;
    END IF;

    incoming := jsonb_build_object('origin','cps_sections',
        'row',to_jsonb(NEW)-'id'-'cree_le'-'texte'-'legacy_sections');
    UPDATE public.cps_sections s
    SET sujets=ARRAY(SELECT DISTINCT item FROM unnest(s.sujets||NEW.sujets) item ORDER BY item),
        legacy_sections=(
            SELECT jsonb_agg(DISTINCT entry)
            FROM jsonb_array_elements(s.legacy_sections||NEW.legacy_sections||jsonb_build_array(incoming)) entry
        )
    WHERE s.id=keeper
      AND (NOT s.sujets @> NEW.sujets
           OR NOT s.legacy_sections @> (NEW.legacy_sections||jsonb_build_array(incoming)));
    RETURN NULL;
END;
$$;

DROP TRIGGER IF EXISTS cps_sections_merge_repeated_text ON public.cps_sections;
CREATE TRIGGER cps_sections_merge_repeated_text
BEFORE INSERT ON public.cps_sections
FOR EACH ROW EXECUTE FUNCTION public.sou9na_merge_repeated_cps_text();
