# Aktier & Udbytte

Streamlit-værktøj med to uafhængige beregninger:

1. **Kursregulering** — realiseret/urealiseret kursgevinst-tab på noterede
   aktier efter **lagerprincippet**.
2. **Udbytte** — bruttoudbytte og kildeskat ud fra det nettobeløb, der er
   modtaget på bankkontoen.

Begge dele genererer en CSV-fil klar til import i e-conomics kassekladde.

Scope: kun noterede aktier — ikke obligationer, finansielle kontrakter
eller andre værdipapirtyper.

## Kør appen

```bash
pip install -r requirements.txt
streamlit run app.py
```

Forsiden (`app.py`) er en simpel landingsside med to knapper. De to
værktøjer ligger som separate sider i `pages/`, og Streamlit viser dem
automatisk i menuen til venstre.

Test med eksempeldataet i `test_data/` — der ligger én fil pr. værktøj.

## Filstruktur

- `parser.py` — indlæser Excel-fil med køb/salg og genkender kolonner fleksibelt
- `validering.py` — tjekker køb/salg-data for fejl/uoverensstemmelser før beregning
- `beregning.py` — selve lagerprincip/FIFO-beregningen (ren Python/pandas, testbar uafhængigt af UI)
- `udbytte.py` — parsing, validering og beregning af udbytte (brutto/kildeskat), også testbar uafhængigt af UI
- `csv_eksport.py` — genererer den semikolon-separerede CSV-fil til e-conomic, bruges af begge værktøjer
- `app.py` — landingsside
- `pages/1_📈_Kursregulering.py` — UI for kursregulering
- `pages/2_💰_Udbytte.py` — UI for udbytte
- `test_data/` — eksempeldata for begge værktøjer, inkl. bevidste fejl og advarsler

## Input-format: Kursregulering

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

### Lagerprincippet kort fortalt

- **Primo kurs er IKKE anskaffelsessummen.** Det er sidste års ultimo-kurs
  (allerede beskattet én gang sidste år).
- **Tilgange i året** har basis = den faktiske købspris.
- Beskatning sker hvert år, uanset om papiret sælges eller ej.
- FIFO afgør, om et solgt stykke stammer fra primo-beholdningen eller en
  tilgang i året, og bruger den tilsvarende basis til at beregne den
  **realiserede** del. Den resterende beholdning ved ultimo giver den
  **urealiserede** del.

## Input-format: Udbytte

Hovedvejen er at **indtaste direkte i en tabel i UI'en** — ingen fil
nødvendig. Har man mange linjer, kan man i stedet uploade en Excel- eller
CSV-fil, som udfylder tabellen automatisk (man kan stadig rette i den
bagefter). Én linje pr. udbyttebetaling:

| Kolonne | Beskrivelse |
|---|---|
| Papirnavn | Navnet på aktien |
| Landekode / Land / ISIN | Landet udbyttet kommer fra (bruges til at slå skattesats op) |
| Type | "Netto" eller "Brutto" — hvilken slags beløb man angiver (se nedenfor) |
| Beløb | Netto- ELLER bruttoudbytte, afhængig af Type |
| Dato | Betalingsdato (valgfri) |

Man angiver ENTEN nettobeløbet (det der reelt blev indsat på
bankkontoen) ELLER bruttobeløbet — det andet regnes automatisk ud fra en
kendt nettoprocent pr. land (se `LANDE_NETTOPROCENT` i `udbytte.py` — ret
eller udvid listen hvis et land mangler eller satsen er forkert).

CSV-filer kan bruge komma eller semikolon som separator, og danske
talformater (fx "18.823,41") — det opdages automatisk.

**Bemærk:** Dette er en bevidst forenklet model. Den opdeler IKKE
udenlandsk kildeskat i "tilbagesøges via selvangivelse" vs. "tilbagesøges
via banken" efter dobbeltbeskatningsoverenskomstens maks-sats — det er en
tax-teknisk detalje, I/revisor skal vurdere manuelt efter behov. Al
kildeskat bogføres som ét samlet tilgodehavende pr. land (dansk/udenlandsk).

## Fortegnskonvention i CSV-eksporten

**Kursregulering:** Balancekontoen (aktiv) får gevinst/tab-beløbet direkte
(positivt = debet = værdistigning). Resultatkontoen får det modsatte
fortegn, så hvert bilag balancerer.

**Udbytte:** Bruttoudbyttet krediteres resultatkontoen (indtægt),
kildeskatten debiteres en tilgodehavende-konto (dansk hhv. udenlandsk), og
nettobeløbet debiteres bankkontoen.

Tjek begge konventioner passer til jeres kontoplan — se docstring i
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
regnskabsdata, bør I overveje adgangsbegrænsning (fx Railway's private
networking, IP-begrænsning, eller en simpel adgangskode i appen), hvis
URL'en ikke skal være offentligt tilgængelig.
