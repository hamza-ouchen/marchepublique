-- Sou9na — canonical tender URL + document enrichment queue.
-- Non destructif : aucune ligne n'est supprimée, aucune référence déplacée.
-- Les doublons historiques conservent leurs scores/verdicts/documents ; seul
-- leur url_key est mis à NULL pour rendre l'index partiel unique.

alter table public.tenders
  add column if not exists url_key text,
  add column if not exists extraction jsonb not null default '{}'::jsonb,
  add column if not exists enriched_at timestamptz,
  add column if not exists enrich_attempts integer not null default 0,
  add column if not exists enrich_next_at timestamptz,
  add column if not exists enrich_error text;

create or replace function public.soukna_canonical_url(raw text)
returns text
language plpgsql
immutable
as $fn$
declare
  v          text := lower(btrim(coalesce(raw, '')));
  scheme     text;
  authority  text;
  rest       text;
  host       text;
  port       text := '';
  path       text;
  query      text := '';
  piece      text;
  cle        text;
  kept       text[] := '{}';
  out_query  text := '';
  resultat   text;
begin
  if v = '' then
    return '';
  end if;

  if v !~ '^[a-z][a-z0-9+.-]*://' then
    v := 'https://' || v;
  end if;

  scheme := substring(v from '^([a-z][a-z0-9+.-]*)://');
  authority := regexp_replace(v, '^[a-z][a-z0-9+.-]*://([^/?#]*).*$', '\1');
  rest := regexp_replace(v, '^[a-z][a-z0-9+.-]*://[^/?#]*', '');
  rest := split_part(rest, '#', 1);

  if position('?' in rest) > 0 then
    path := split_part(rest, '?', 1);
    query := substring(rest from position('?' in rest) + 1);
  else
    path := rest;
    query := '';
  end if;

  authority := regexp_replace(authority, '^.*@', '');
  if authority ~ ':[0-9]+$' then
    port := substring(authority from ':([0-9]+)$');
    host := regexp_replace(authority, ':[0-9]+$', '');
  else
    host := authority;
  end if;

  host := regexp_replace(host, '^www\.', '');
  if (scheme = 'http' and port = '80') or (scheme = 'https' and port = '443') then
    port := '';
  end if;

  path := regexp_replace(path, '/{2,}', '/', 'g');
  if length(path) > 1 and right(path, 1) = '/' then
    path := left(path, length(path) - 1);
  end if;
  if path = '' then
    path := '/';
  end if;

  if query <> '' then
    foreach piece in array string_to_array(query, '&') loop
      piece := btrim(piece);
      continue when piece = '';
      cle := lower(split_part(piece, '=', 1));
      continue when cle ~ '^utm_';
      continue when cle in ('fbclid', 'gclid', 'mc_cid', 'mc_eid', '_ga', 'igshid', 'msclkid');
      kept := array_append(kept, piece);
    end loop;
    if coalesce(array_length(kept, 1), 0) > 0 then
      select string_agg(k, '&' order by k) into out_query from unnest(kept) as k;
    end if;
  end if;

  resultat := scheme || '://' || host;
  if port <> '' then
    resultat := resultat || ':' || port;
  end if;
  resultat := resultat || path;
  if out_query <> '' then
    resultat := resultat || '?' || out_query;
  end if;
  return resultat;
end;
$fn$;

-- Backfill : une seule ligne par URL canonique garde sa clé. Les autres
-- restent en base avec url_key NULL (aucune suppression, aucun déplacement).
update public.tenders
set url_key = public.soukna_canonical_url(source_url)
where source_url is not null and btrim(source_url) <> '';

with ranked as (
  select ctid,
         row_number() over (
           partition by url_key
           order by date_collecte desc nulls last,
                    cree_le desc nulls last,
                    reference desc
         ) as rn
  from public.tenders
  where url_key is not null
)
update public.tenders t
set url_key = null
from ranked r
where t.ctid = r.ctid and r.rn > 1;

create unique index if not exists idx_tenders_url_key
  on public.tenders (url_key)
  where url_key is not null;

create index if not exists idx_tenders_enrich_queue
  on public.tenders (enrich_next_at)
  where enriched_at is null;
