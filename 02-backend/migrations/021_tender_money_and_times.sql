ALTER TABLE public.tenders
    ADD COLUMN IF NOT EXISTS heure_publication time(0),
    ADD COLUMN IF NOT EXISTS heure_remise time(0);

COMMENT ON COLUMN public.tenders.heure_publication IS 'Heure locale Africa/Casablanca constatée dans la source.';
COMMENT ON COLUMN public.tenders.heure_remise IS 'Heure locale Africa/Casablanca de clôture des dépôts.';

CREATE OR REPLACE FUNCTION public.sou9na_round_tender_mad()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    NEW.montant_mad := round(NEW.montant_mad, 2);
    NEW.caution_mad := round(NEW.caution_mad, 2);
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS sou9na_round_tender_mad ON public.tenders;
CREATE TRIGGER sou9na_round_tender_mad
BEFORE INSERT OR UPDATE OF montant_mad, caution_mad ON public.tenders
FOR EACH ROW EXECUTE FUNCTION public.sou9na_round_tender_mad();

UPDATE public.tenders
SET montant_mad = round(montant_mad, 2), caution_mad = round(caution_mad, 2)
WHERE scale(montant_mad) <> 2 OR scale(caution_mad) <> 2;
