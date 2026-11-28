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
