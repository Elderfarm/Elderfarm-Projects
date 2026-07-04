-- Grundskema for Aktier & Udbytte-platformen.
--
-- Designet multi-tenant-forberedt (alt hænger på company_id + Row Level
-- Security), men første version af appen forudsætter kun én bruger pr.
-- virksomhed og ingen rolle-administration i UI'en endnu.

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- Virksomheder og brugere
-- ---------------------------------------------------------------------------

create table companies (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  cvr text,
  created_at timestamptz not null default now()
);

-- Én række pr. Supabase Auth-bruger. Knytter brugeren til en virksomhed.
create table profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  company_id uuid not null references companies (id) on delete cascade,
  full_name text,
  role text not null default 'admin' check (role in ('admin', 'medarbejder')),
  created_at timestamptz not null default now()
);

create index profiles_company_id_idx on profiles (company_id);

-- ---------------------------------------------------------------------------
-- Depoter og værdipapirer
-- ---------------------------------------------------------------------------

create table depots (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies (id) on delete cascade,
  name text not null,
  bank text,
  created_at timestamptz not null default now()
);

create index depots_company_id_idx on depots (company_id);

create table securities (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies (id) on delete cascade,
  isin text,
  name text not null,
  currency text not null default 'DKK',
  created_at timestamptz not null default now()
);

create index securities_company_id_idx on securities (company_id);

-- ---------------------------------------------------------------------------
-- Udbytte
-- ---------------------------------------------------------------------------

create table dividends (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies (id) on delete cascade,
  depot_id uuid references depots (id) on delete set null,
  security_id uuid references securities (id) on delete set null,
  security_name text not null,
  country_code text not null,
  payment_date date,
  -- Det beløb brugeren indtastede, og hvilken slags det er. Det andet
  -- beløb (gross/net) udregnes og gemmes, så vi ikke skal genberegne det
  -- hver gang (og så historikken er stabil, selvom landeprocenter ændres).
  amount numeric(14, 2) not null,
  amount_type text not null check (amount_type in ('netto', 'brutto')),
  gross_amount numeric(14, 2) not null,
  net_amount numeric(14, 2) not null,
  withholding_tax numeric(14, 2) not null,
  is_domestic boolean not null,
  created_at timestamptz not null default now(),
  created_by uuid references profiles (id) on delete set null
);

create index dividends_company_id_idx on dividends (company_id);

-- ---------------------------------------------------------------------------
-- Kursregulering (lagerprincip)
-- ---------------------------------------------------------------------------

create table price_regulations (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies (id) on delete cascade,
  depot_id uuid references depots (id) on delete set null,
  security_id uuid references securities (id) on delete set null,
  security_name text not null,
  isin text,
  year int not null,
  primo_qty numeric(14, 4) not null default 0,
  primo_price numeric(14, 4) not null default 0,
  additions_qty numeric(14, 4) not null default 0,
  additions_amount numeric(14, 2) not null default 0,
  disposals_qty numeric(14, 4) not null default 0,
  disposals_amount numeric(14, 2) not null default 0,
  ultimo_qty numeric(14, 4) not null default 0,
  ultimo_price numeric(14, 4) not null default 0,
  realized_gain numeric(14, 2) not null default 0,
  unrealized_gain numeric(14, 2) not null default 0,
  created_at timestamptz not null default now(),
  created_by uuid references profiles (id) on delete set null
);

create index price_regulations_company_id_idx on price_regulations (company_id);

-- ---------------------------------------------------------------------------
-- Posteringer og eksporter
-- ---------------------------------------------------------------------------

-- Bogføringsforslag afledt af en udbytte- eller kursreguleringsberegning.
-- Flere rækker med samme voucher_no udgør ét bilag, der altid balancerer.
create table postings (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies (id) on delete cascade,
  source_type text not null check (source_type in ('dividend', 'price_regulation')),
  source_id uuid not null,
  voucher_no int not null,
  posting_date date not null,
  account text not null,
  amount numeric(14, 2) not null,
  text text not null,
  created_at timestamptz not null default now()
);

create index postings_company_id_idx on postings (company_id);
create index postings_source_idx on postings (source_type, source_id);

create table exports (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies (id) on delete cascade,
  export_type text not null check (export_type in ('dividend', 'price_regulation')),
  file_name text not null,
  row_count int not null,
  created_at timestamptz not null default now(),
  created_by uuid references profiles (id) on delete set null
);

create index exports_company_id_idx on exports (company_id);

-- ---------------------------------------------------------------------------
-- Row Level Security: en bruger kan kun se/ændre data for sin egen virksomhed
-- ---------------------------------------------------------------------------

create function current_company_id() returns uuid
language sql stable
as $$
  select company_id from profiles where id = auth.uid();
$$;

alter table companies enable row level security;
alter table profiles enable row level security;
alter table depots enable row level security;
alter table securities enable row level security;
alter table dividends enable row level security;
alter table price_regulations enable row level security;
alter table postings enable row level security;
alter table exports enable row level security;

create policy "Se egen virksomhed" on companies
  for select using (id = current_company_id());

create policy "Se profiler i egen virksomhed" on profiles
  for select using (company_id = current_company_id());

create policy "Adgang til egne depoter" on depots
  for all using (company_id = current_company_id())
  with check (company_id = current_company_id());

create policy "Adgang til egne værdipapirer" on securities
  for all using (company_id = current_company_id())
  with check (company_id = current_company_id());

create policy "Adgang til egne udbytter" on dividends
  for all using (company_id = current_company_id())
  with check (company_id = current_company_id());

create policy "Adgang til egne kursreguleringer" on price_regulations
  for all using (company_id = current_company_id())
  with check (company_id = current_company_id());

create policy "Adgang til egne posteringer" on postings
  for all using (company_id = current_company_id())
  with check (company_id = current_company_id());

create policy "Adgang til egne eksporter" on exports
  for all using (company_id = current_company_id())
  with check (company_id = current_company_id());
