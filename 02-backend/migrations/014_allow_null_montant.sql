-- Unknown amounts must stay NULL instead of a fake positive sentinel.
ALTER TABLE public.tenders DROP CONSTRAINT IF EXISTS tenders_montant_mad_check;
ALTER TABLE public.tenders ADD CONSTRAINT tenders_montant_mad_check
    CHECK (montant_mad IS NULL OR montant_mad > 0);

UPDATE public.tenders SET montant_mad = NULL WHERE montant_mad = 1;
