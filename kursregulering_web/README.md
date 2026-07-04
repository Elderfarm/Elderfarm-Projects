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
2. Kør migrationerne i `supabase/migrations/` i rækkefølge (via SQL-editoren
   i Supabase-dashboardet, eller `supabase db push` med Supabase CLI) —
   `0001_init.sql` opretter skemaet, `0002_signup_trigger.sql` gør at en ny
   bruger automatisk får oprettet sin egen virksomhed
3. Kopiér Project URL og anon key ind i `.env.local`
4. Gå til `/signup` og opret jeres første bruger — virksomhed + profil
   oprettes automatisk (første bruger bliver admin for sin egen virksomhed)

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
- `supabase/migrations/` — databaseskema + trigger til selvbetjent tilmelding

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

- Multi-tenant UI (flere brugere/roller pr. virksomhed — databasen
  understøtter det, men der er ingen invitations-/rolle-administration i UI'en)
- AI-chat-assistent
- PDF-rapporter, aktivitetslog/revisionsspor, automatisk backup
- Dark mode
- Diagrammer (Recharts er installeret, men ikke taget i brug endnu)

## Deploy til Railway

Mappen indeholder `railway.json`, så Railway kan bygge og starte appen
automatisk (Nixpacks genkender `package.json`). Startkommandoen er testet
lokalt mod Railways `$PORT`-konvention.

1. Opret et nyt projekt i Railway og forbind det til dette GitHub-repo
2. Sæt **Root Directory** til `kursregulering_web`
3. Tilføj miljøvariablerne `NEXT_PUBLIC_SUPABASE_URL` og
   `NEXT_PUBLIC_SUPABASE_ANON_KEY` under **Variables** (samme værdier som i
   `.env.local`) — uden dem er `/dashboard` ikke login-beskyttet, se
   "Sikkerhed" nedenfor
4. Railway bygger med `npm run build` og starter med
   `npm run start -- -p $PORT`
5. Under **Settings** → **Networking** → **Generate Domain** får du en
   `*.up.railway.app`-URL

Next.js-appen er også oplagt til Vercel (byggeren er lavet af samme team og
kræver typisk ingen ekstra konfiguration — bare forbind repoet og sæt
Root Directory + de samme to miljøvariabler), hvis I foretrækker det.

## Sikkerhed

- `xlsx`-pakken blev bevidst undgået (kendt, uafhjulpet prototype
  pollution-sårbarhed) — Excel-parsing bruger `exceljs` i stedet.
- `proxy.ts` lukker requests igennem UDEN login-tjek, hvis
  Supabase-miljøvariablerne ikke er sat — det er kun beregnet til lokal
  udvikling. **Sæt `.env.local` op før produktion**, ellers er
  `/dashboard` reelt offentligt tilgængeligt.
