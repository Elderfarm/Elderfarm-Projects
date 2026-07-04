# Aktier & Udbytte — webplatform

Next.js/Supabase-version af kursregulerings- og udbytteværktøjet. Bygget
som en erstatning for Streamlit-værktøjet i `../kursregulering`, startende
med kerne-modulerne. Auth, AI-chat, PDF-rapporter, dark mode m.m. er
bevidst ikke med i denne version — se "Hvad mangler" nederst.

## Kom i gang

```bash
npm install
cp .env.local.example .env.local   # udfyld med jeres Supabase-projekt
npm run dev
```

Uden `.env.local` udfyldt kører appen stadig (kursregulering og udbytte
virker fuldt lokalt i browseren), men login er slået fra, og intet gemmes.
Dashboardet viser en tydelig besked om at forbinde Supabase.

### Sæt Supabase op

1. Opret et projekt på [supabase.com](https://supabase.com)
2. Kør migrationen i `supabase/migrations/0001_init.sql` (via SQL-editoren i
   Supabase-dashboardet, eller `supabase db push` med Supabase CLI)
3. Kopiér Project URL og anon key ind i `.env.local`
4. Opret jeres første bruger under Authentication -> Users, og indsæt en
   tilsvarende række i `companies` og `profiles` via SQL-editoren:

```sql
insert into companies (name) values ('Jeres Firma') returning id;
-- brug id'et herfra og bruger-id'et fra Authentication -> Users:
insert into profiles (id, company_id, full_name) values ('<bruger-id>', '<company-id>', 'Dit navn');
```

Der er ikke (endnu) en selvbetjent tilmeldingsside — se "Hvad mangler".

## Struktur

- `src/lib/calculations/` — ren beregningslogik (ingen UI/Supabase-afhængighed), porteret fra og verificeret mod den validerede Python-version i `../kursregulering`
  - `udbytte.ts` — brutto/netto/kildeskat pr. land
  - `kursregulering.ts` — FIFO/lagerprincip-beregning + validering
- `src/lib/csv/economic.ts` — CSV-generator til e-conomics kassekladde (samme format som Python-versionen)
- `src/lib/import/` — fleksibel Excel/CSV-parsing til fil-upload
- `src/lib/supabase/` — browser-/server-klienter + `hasSupabaseEnv()`
- `src/components/ui/` — design-system (Card, Button, Input, Table, Badge, Callout, StatCard)
- `src/app/dashboard/` — Dashboard, Udbytte, Kursregulering, Eksporter
- `src/proxy.ts` — auth-gating (Next.js 16's afløser for `middleware.ts`)
- `supabase/migrations/0001_init.sql` — databaseskema

## Verificér beregningslogikken

```bash
npx tsx scripts/verify-udbytte.ts
npx tsx scripts/verify-kursregulering.ts
npx tsx scripts/verify-csv.ts
```

Disse scripts sammenligner output mod de samme facit-tal som
Python-versionen er verificeret imod (bl.a. tal fra en rigtig
udbytte-skabelon).

## Designsystem

Lyst tema (hvid baggrund, grå nuancer, mørkeblå accent `#1E3A8A`, grøn
succes, rød fejl), 16px rounded corners, bløde skygger — defineret som
CSS-variabler i `src/app/globals.css` (Tailwind v4's `@theme`-syntaks).

## Hvad mangler (bevidst fravalgt i denne omgang)

Per aftale er følgende IKKE bygget i denne version, men kan tilføjes i
separate omgange:

- Selvbetjent tilmelding (virksomhed + bruger oprettes i dag via SQL)
- Multi-tenant UI (flere brugere/roller pr. virksomhed)
- AI-chat-assistent
- PDF-rapporter, aktivitetslog/revisionsspor, automatisk backup
- Dark mode
- Diagrammer (Recharts er installeret, men ikke taget i brug endnu)

## Sikkerhed

- `xlsx`-pakken blev bevidst undgået (kendt, uafhjulpet prototype
  pollution-sårbarhed) — Excel-parsing bruger `exceljs` i stedet.
- `proxy.ts` lukker requests igennem UDEN login-tjek, hvis
  Supabase-miljøvariablerne ikke er sat — det er kun beregnet til lokal
  udvikling. **Sæt `.env.local` op før produktion**, ellers er
  `/dashboard` reelt offentligt tilgængeligt.
