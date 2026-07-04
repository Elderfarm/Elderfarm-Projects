-- Selvbetjent tilmelding: når en ny bruger opretter sig via Supabase Auth
-- (supabase.auth.signUp), oprettes automatisk en virksomhed + profil, så
-- man ikke længere skal indsætte rækkerne manuelt via SQL-editoren.
--
-- Kører med SECURITY DEFINER, så den kan skrive til `companies`/`profiles`
-- uafhængigt af Row Level Security — det er sikkert her, fordi funktionen
-- kun trigges af Supabase Auth selv (auth.users), ikke af klientkode.

create function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
declare
  ny_company_id uuid;
  firmanavn text;
begin
  firmanavn := coalesce(new.raw_user_meta_data ->> 'company_name', 'Ny virksomhed');

  insert into companies (name) values (firmanavn)
  returning id into ny_company_id;

  insert into profiles (id, company_id, full_name)
  values (new.id, ny_company_id, new.raw_user_meta_data ->> 'full_name');

  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function public.handle_new_user();
