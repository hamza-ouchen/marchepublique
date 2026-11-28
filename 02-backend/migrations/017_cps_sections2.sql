-- Une empreinte est unique par consultation. Deux consultations peuvent
-- référencer les mêmes octets dans Storage.
alter table public.tender_documents drop constraint if exists tender_documents_sha256_key;

create table if not exists public.cps_sections2 (
  document_id bigint not null references public.tender_documents(id) on delete cascade,
  section_no integer not null,
  numero text,
  titre text,
  texte text not null,
  pages_section text,
  sujets text[] not null,
  primary key (document_id, section_no)
);

alter table public.cps_sections2 enable row level security;

create or replace function public.soukna_cps_section_topics(contenu text)
returns text[]
language sql
immutable
as $$
  select array_remove(array[
    case when contenu ~* '(caution provisoire|garantie financière|garantie financiere)' then 'caution' end,
    case when contenu ~* '(montant estimatif|estimation du co[uû]t|budget pr[ée]visionnel|estimation du ma[iî]tre)' then 'montant' end,
    case when contenu ~* '(d[ée]lai d.ex[ée]cution|dur[ée]e d.ex[ée]cution|remise des plis|r[ée]ception des devis)' then 'dates_et_delais' end,
    case when contenu ~* '(qualification|certification|classement|agr[ée]ment)' then 'qualifications' end,
    case when contenu ~* '(p[ée]nalit[ée]|retenue de garantie)' then 'penalites' end,
    case when contenu ~* '(visite des lieux|reconnaissance des lieux)' then 'visite' end,
    case when contenu ~* '(pi[èe]ces (administratives|techniques)|dossier administratif)' then 'pieces' end,
    case when contenu ~* '(lot unique|allotissement|lot n)' then 'lots' end
  ], null);
$$;

create or replace function public.soukna_sync_cps_section2()
returns trigger
language plpgsql
as $$
declare
  themes text[];
begin
  if tg_op in ('UPDATE', 'DELETE') then
    delete from public.cps_sections2 where document_id = old.document_id
      and section_no = old.section_no;
  end if;
  if tg_op <> 'DELETE' then
    themes := public.soukna_cps_section_topics(concat_ws(' ', new.titre, new.texte));
    if cardinality(themes) > 0 then
      insert into public.cps_sections2 values
        (new.document_id, new.section_no, new.numero, new.titre, new.texte, new.pages_section, themes)
      on conflict (document_id, section_no) do update set
        numero = excluded.numero, titre = excluded.titre, texte = excluded.texte,
        pages_section = excluded.pages_section, sujets = excluded.sujets;
    end if;
  end if;
  return null;
end;
$$;

create or replace trigger cps_sections_sync_sections2
after insert or update or delete on public.cps_sections
for each row execute function public.soukna_sync_cps_section2();

insert into public.cps_sections2 (document_id, section_no, numero, titre, texte, pages_section, sujets)
select s.document_id, s.section_no, s.numero, s.titre, s.texte, s.pages_section, topics.sujets
from public.cps_sections s
cross join lateral (select public.soukna_cps_section_topics(concat_ws(' ', s.titre, s.texte)) as sujets) topics
where cardinality(topics.sujets) > 0
on conflict (document_id, section_no) do nothing;
