-- Index de recherche pour le pré-filtrage anti-doublon de scrape_portal.import_to_db.
-- Non unique : la base historique contient encore des URLs en double (1532).
-- Le filtre applicatif (URL canonique puis référence) garantit qu'aucun NOUVEAU
-- doublon n'est inséré. Un nettoyage historique nécessite une migration dédiée
-- avec déplacement des scores/verdicts/documents dépendants (non destructif).
create index if not exists idx_tenders_source_url
  on public.tenders (source_url)
  where source_url is not null and source_url <> '';
