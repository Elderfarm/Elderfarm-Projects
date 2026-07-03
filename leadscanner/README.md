# Leadscanner 📡

En selvbetjenings-platform til at søge, berige og eksportere danske virksomhedsdata (B2B-leads) — bygget til at være hurtigere og mere gennemsigtig end traditionelle data-udbydere.

## Hvad gør det anderledes

- **Datakvalitetsscore** på hver virksomhed (completeness + "sidst verificeret") — ingen skjulte huller i dataen
- **Instant søgning/filtrering** på branche, by, ansatte og status — ingen salgsdemo krævet
- **Ét-klik CSV-eksport** direkte fra søgeresultaterne
- **Berigelse ud over rå CVR-data**: officiel hjemmeside + offentlig kontaktinfo, fundet via websøgning

## Datakilde og lovlighed

Al kernedata kommer fra **CVR** (Det Centrale Virksomhedsregister), som er offentligt og frit tilgængeligt dansk erhvervsregister — det er lovligt at indsamle og videresælge denne data.

Systemet har to lag:

1. **Simuleret demo-mode** (default) — genererer realistisk, men opdigtet testdata, så du kan bygge og teste UI/eksport uden ekstern adgang.
2. **Live CVR-data** — kræver at *du* opretter en gratis konto på [datafordeler.dk](https://datafordeler.dk) og sætter miljøvariablerne:
   ```
   CVR_API_USER=dit-brugernavn
   CVR_API_PASSWORD=dit-kodeord
   ```
   Herefter henter `cvr_client.py` automatisk rigtige virksomheder fra Datafordelerens CVR-søge-API i stedet for simulerede data. Jeg kan ikke oprette denne konto for dig — det er et personligt/virksomheds-login.

Enkeltopslag kan desuden beriges via [cvrapi.dk](https://cvrapi.dk) (gratis, ingen login, men rate-begrænset).

## Juridisk/compliance-note (vigtig)

- **Selve indsamlingen af CVR-data er ukompliceret** — det er åbne offentlige data.
- **Hvis dine kunder bruger dataen til direkte markedsføring** (koldt salg via email/SMS/telefon), gælder markedsføringslovens regler om samtykke i Danmark — også i B2B-sammenhæng, med visse undtagelser for eksisterende kunderelationer. Det er købernes ansvar at overholde dette, men det bør fremgå tydeligt af dine vilkår/salgsvilkår, så det ikke bliver en overraskelse.
- Anbefaling: skriv en kort brugsvejledning/disclaimer på landing page/vilkår, når du går i produktion.

## Kom i gang lokalt

```bash
cd leadscanner
pip install -r requirements.txt
python app.py
```

Åbn `http://localhost:5000`, opret en konto, og gå til **Indsamling** for at køre din første dataindsamling (kører i simuleret mode indtil CVR-credentials er sat).

## Arkitektur

```
app.py           — Flask-app: auth, søgning/filtrering, eksport, indsamlings-trigger
models.py        — SQLAlchemy-modeller: User, Company, ExportLog, CollectionRun
cvr_client.py    — CVR-datakilde (live + simuleret fallback)
enrichment.py    — Datakvalitetsscore + website/kontakt-finder
pipeline.py      — Indsamlings-motor (CLI + kaldes fra app.py)
templates/       — Jinja-templates (søgning, virksomhedsdetalje, indsamling)
static/css/      — Eget visuelt tema
```

## Prismodel (struktur klar, betaling ikke koblet på endnu)

`User.plan` understøtter `gratis` / `pro` / `enterprise` med forskellige månedlige eksportgrænser (se `PLAN_LIMITS` i `models.py`) — samme mønster som Postmester. Stripe-integration til rigtig betaling er **ikke** bygget endnu; tilføjes når du er klar til at sælge adgang.

## Ikke inkluderet endnu

- Betalingsflow (Stripe)
- Bulk/skaleret live CVR-indsamling (kræver dine Datafordeler-credentials)
- Automatisk/planlagt genindsamling (kan tilføjes som cron-job der kalder `pipeline.run_collection`)
