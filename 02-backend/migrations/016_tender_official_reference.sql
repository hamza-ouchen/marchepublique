alter table public.tenders
  add column if not exists reference_officielle text;

create or replace function public.soukna_reference_officielle(reference_interne text)
returns text
language sql
immutable
strict
as $$
  select nullif(btrim(regexp_replace(
    regexp_replace(reference_interne, '^portal:', ''),
    ' \[(consultation:[^:]+:[0-9]+|bdc:[0-9]+)\]( #[0-9]+)?$', ''
  )), '');
$$;

update public.tenders
set reference_officielle = public.soukna_reference_officielle(reference)
where reference_officielle is null;

create or replace function public.soukna_default_tender_reference_officielle()
returns trigger
language plpgsql
as $$
begin
  if new.reference_officielle is null then
    new.reference_officielle := public.soukna_reference_officielle(new.reference);
  end if;
  return new;
end;
$$;

create or replace trigger tenders_default_reference_officielle
before insert on public.tenders
for each row execute function public.soukna_default_tender_reference_officielle();
