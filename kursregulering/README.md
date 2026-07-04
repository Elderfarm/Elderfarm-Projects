# Kursregulering af noterede aktier

Streamlit-værktøj til at beregne realiseret og urealiseret kursgevinst/-tab
på noterede aktier efter **lagerprincippet**, og generere en CSV-fil klar
til import i e-conomics kassekladde.

Scope: kun noterede aktier — ikke obligationer, finansielle kontrakter
eller andre værdipapirtyper.

## Kør appen

```bash
pip install -r requirements.txt
streamlit run app.py
```

Upload din egen Excel-fil, eller test med eksempeldataet i
`test_data/eksempel_transaktioner.xlsx` (generet af `test_data/generer_testdata.py`).

## Filstruktur

- `parser.py` — indlæser Excel-filen og genkender kolonner fleksibelt
- `validering.py` — tjekker data for fejl/uoverensstemmelser før beregning
- `beregning.py` — selve lagerprincip/FIFO-beregningen (ren Python/pandas, testbar uafhængigt af UI)
- `csv_eksport.py` — genererer den semikolon-separerede CSV-fil til e-conomic
- `app.py` — Streamlit-UI'en, der binder det hele sammen
- `test_data/` — eksempel-Excel med 6 værdipapirer, inkl. bevidste fejl og advarsler

## Input-format

Excel-arket skal have én række pr. transaktion, med kolonner (navnene
genkendes fleksibelt, fx "Navn" eller "Papirnavn"):

| Kolonne | Beskrivelse |
|---|---|
| ISIN / Papirnavn | Mindst én af dem skal være udfyldt |
| Type | Primo / Tilgang / Afgang / Ultimo |
| Dato | Transaktionsdato |
| Antal | Antal stk. |
| Kurs | Kurs pr. stk. |
| Beløb | Antal × Kurs — kan stå tom og udregnes automatisk |
| Valuta | Default DKK, hvis kolonnen mangler |

## Lagerprincippet kort fortalt

- **Primo kurs er IKKE anskaffelsessummen.** Det er sidste års ultimo-kurs
  (allerede beskattet én gang sidste år).
- **Tilgange i året** har basis = den faktiske købspris.
- Beskatning sker hvert år, uanset om papiret sælges eller ej.
- FIFO afgør, om et solgt stykke stammer fra primo-beholdningen eller en
  tilgang i året, og bruger den tilsvarende basis til at beregne den
  **realiserede** del. Den resterende beholdning ved ultimo giver den
  **urealiserede** del.

## Fortegnskonvention i CSV-eksporten

Balancekontoen (aktiv) får gevinst/tab-beløbet direkte (positivt = debet =
værdistigning). Resultatkontoen får det modsatte fortegn, så hvert bilag
balancerer. Tjek at det passer til jeres kontoplan — se docstring i
`csv_eksport.py`.

## Deploy til Railway

Mappen indeholder `Procfile` og `railway.json`, så Railway kan bygge og
starte appen automatisk (Nixpacks genkender `requirements.txt`).

1. Opret et nyt projekt i Railway og forbind det til dette GitHub-repo
2. Sæt **Root Directory** til `kursregulering`
3. Railway finder selv `Procfile`/`railway.json` og starter appen med
   `streamlit run app.py --server.port=$PORT --server.address=0.0.0.0`
4. Når deployet er kørt, får du en `*.up.railway.app`-URL under fanen "Settings" → "Networking" → "Generate Domain"

**Bemærk:** Appen har ingen login. Da den kan behandle interne
kursreguleringsdata, bør I overveje adgangsbegrænsning (fx Railway's
private networking, IP-begrænsning, eller en simpel adgangskode i appen),
hvis URL'en ikke skal være offentligt tilgængelig.
