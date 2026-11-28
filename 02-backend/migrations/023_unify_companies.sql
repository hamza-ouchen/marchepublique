-- Execute in a transaction. This cutover was prepared for an empty legacy
-- company table; an unexpected write aborts so no profile can be discarded.
LOCK TABLE public.companies, public.entreprises IN ACCESS EXCLUSIVE MODE;
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM public.entreprises) THEN
        RAISE EXCEPTION 'Legacy companies appeared before cutover; reconcile them before consolidation';
    END IF;
END;
$$;

ALTER TABLE public.companies
    ADD COLUMN company_id text GENERATED ALWAYS AS (id::text) STORED UNIQUE,
    ADD COLUMN capacite_mad numeric CHECK (capacite_mad > 0),
    ADD COLUMN qualifications text[] NOT NULL DEFAULT '{}',
    ADD COLUMN historique jsonb NOT NULL DEFAULT '[]',
    ADD COLUMN matching_enabled boolean NOT NULL DEFAULT false,
    ADD COLUMN IF NOT EXISTS init_status text DEFAULT 'ready',
    ADD COLUMN IF NOT EXISTS init_started_at timestamptz,
    ADD COLUMN IF NOT EXISTS init_error text,
    ADD COLUMN IF NOT EXISTS user_id uuid;

ALTER TABLE public.companies
    ALTER COLUMN init_status SET DEFAULT 'ready';
UPDATE public.companies SET init_status='ready' WHERE init_status IS NULL;
ALTER TABLE public.companies
    ALTER COLUMN init_status SET NOT NULL,
    ADD CONSTRAINT companies_matching_init_status_check CHECK (init_status IN ('ready','running','error'));

-- Keep references to the public matching ID, which now comes from the account UUID.
DO $$
DECLARE link record;
BEGIN
    FOR link IN
        SELECT conrelid::regclass AS dependent_table, conname, pg_get_constraintdef(oid) AS definition
        FROM pg_constraint WHERE contype='f' AND confrelid='public.entreprises'::regclass
    LOOP
        EXECUTE format('ALTER TABLE %s DROP CONSTRAINT %I', link.dependent_table, link.conname);
        EXECUTE format('ALTER TABLE %s ADD CONSTRAINT %I %s', link.dependent_table, link.conname,
                       regexp_replace(link.definition, 'REFERENCES (public\.)?entreprises\(',
                                      'REFERENCES public.companies('));
    END LOOP;
END;
$$;

DROP TABLE public.entreprises;

-- Read projection for matching, verdicts and distribution.
CREATE VIEW public.company_matching_profiles WITH (security_invoker=true) AS
SELECT company_id, name AS nom, email, phone AS whatsapp,
       coalesce(sectors[1],'autre') AS secteur, coalesce(regions[1],'autre') AS region,
       capacite_mad, qualifications, historique,
       jsonb_build_object('whatsapp',channel_whatsapp,'email',channel_email) AS canaux_optin,
       trial_started_at::date AS essai_debut,
       CASE WHEN status='suspended' THEN 'suspendu'
            WHEN plan='trial' THEN 'essai' ELSE 'actif' END AS statut,
       created_at AS cree_le, init_status, init_started_at, init_error, user_id
FROM public.companies
WHERE matching_enabled;

-- Older consumers can read the historical name during deployment; this view
-- holds no rows of its own and can be removed after they are upgraded.
CREATE VIEW public.entreprises WITH (security_invoker=true) AS
SELECT * FROM public.company_matching_profiles;

-- The draft company-document migration formerly altered the legacy table.
CREATE TABLE IF NOT EXISTS public.company_documents (
    company_id uuid NOT NULL REFERENCES public.companies(id) ON DELETE CASCADE,
    sha256 text NOT NULL,
    filename text NOT NULL,
    pdf bytea NOT NULL CHECK (octet_length(pdf) BETWEEN 1 AND 2097152),
    uploaded_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (company_id, sha256)
);
ALTER TABLE public.company_documents ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON public.company_documents FROM PUBLIC, anon, authenticated;
