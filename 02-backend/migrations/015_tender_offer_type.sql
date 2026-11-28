-- La nature de l'avis est distincte de son secteur d'activité.
alter table public.tenders
  add column if not exists offer_type text;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conrelid = 'public.tenders'::regclass
      and conname = 'tenders_offer_type_check'
  ) then
    alter table public.tenders add constraint tenders_offer_type_check
      check (offer_type in ('appel_offres', 'consultation', 'bon_de_commande'));
  end if;
end;
$$;

-- La durée d'exécution est différente du temps avant la remise des offres.
alter table public.tenders
  alter column delai_jours drop not null;
