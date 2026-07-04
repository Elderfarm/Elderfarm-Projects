"""
Genererer en eksempel-Excel-fil med transaktionsdata for 6 værdipapirer.

Filen bruges til at teste hele flowet (validering, beregning, CSV-eksport)
uden at skulle bruge en rigtig kundefil. Den indeholder bevidst:
- Nogle "rene" papirer uden fejl/advarsler
- Et papir med en dato-rækkefølge-advarsel
- Et papir med en dublet-advarsel
- Et papir uden Ultimo-linje (fejl)
- Et papir med negativt antal og saldo-uoverensstemmelse (fejl)
- Et papir med manglende kurs på en linje (fejl)

Kør scriptet med: python generer_testdata.py
"""
import openpyxl
from pathlib import Path

# Kolonnerne bruger bevidst "Navn" i stedet for "Papirnavn" for at teste
# den fleksible kolonnegenkendelse i parser.py.
KOLONNER = ["ISIN", "Navn", "Type", "Dato", "Antal", "Kurs", "Beløb", "Valuta"]

# Hver tuple: (isin, navn, type, dato, antal, kurs, beløb, valuta)
# Beløb er sat til None (tom) mange steder, så parseren selv skal udregne den.
RAEKKER = [
    # --- Novo Nordisk B: rent eksempel med både realiseret og urealiseret gevinst ---
    ("DK0060534915", "Novo Nordisk B", "Primo", "2024-01-01", 100, 700, None, "DKK"),
    ("DK0060534915", "Novo Nordisk B", "Tilgang", "2024-03-15", 50, 800, None, "DKK"),
    ("DK0060534915", "Novo Nordisk B", "Afgang", "2024-09-10", 30, 900, None, "DKK"),
    ("DK0060534915", "Novo Nordisk B", "Ultimo", "2024-12-31", 120, 850, None, "DKK"),

    # --- Volvo B: advarsel, afgangsdato ligger før tilgangsdato ---
    ("SE0000115446", "Volvo B", "Primo", "2024-01-01", 200, 220, None, "DKK"),
    ("SE0000115446", "Volvo B", "Tilgang", "2024-05-10", 100, 230, None, "DKK"),
    ("SE0000115446", "Volvo B", "Afgang", "2024-04-01", 50, 240, None, "DKK"),
    ("SE0000115446", "Volvo B", "Ultimo", "2024-12-31", 250, 235, None, "DKK"),

    # --- Ørsted: nyt køb i året, ingen Primo-linje (skal give OK, ikke fejl) ---
    (None, "Ørsted", "Tilgang", "2024-02-15", 80, 550, None, "DKK"),
    (None, "Ørsted", "Ultimo", "2024-12-31", 80, 600, None, "DKK"),

    # --- Genmab: mangler Ultimo-linje -> FEJL ---
    ("DK0010272202", "Genmab", "Primo", "2024-01-01", 60, 1800, None, "DKK"),
    ("DK0010272202", "Genmab", "Tilgang", "2024-03-01", 20, 1900, None, "DKK"),
    ("DK0010272202", "Genmab", "Afgang", "2024-06-01", 30, 2000, None, "DKK"),

    # --- Ambu B: negativt antal ved tilgang + saldo stemmer ikke -> FEJL ---
    ("DK0106223732", "Ambu B", "Primo", "2024-01-01", 150, 120, None, "DKK"),
    ("DK0106223732", "Ambu B", "Tilgang", "2024-04-20", -10, 130, None, "DKK"),
    ("DK0106223732", "Ambu B", "Afgang", "2024-08-15", 40, 140, None, "DKK"),
    ("DK0106223732", "Ambu B", "Ultimo", "2024-12-31", 130, 125, None, "DKK"),

    # --- Pandora: dublet-linje (advarsel) + manglende kurs (fejl) ---
    ("DK0060497719", "Pandora", "Primo", "2024-01-01", 300, 400, None, "DKK"),
    ("DK0060497719", "Pandora", "Tilgang", "2024-03-01", 50, 420, None, "DKK"),
    ("DK0060497719", "Pandora", "Tilgang", "2024-03-01", 50, 420, None, "DKK"),  # dublet
    ("DK0060497719", "Pandora", "Afgang", "2024-07-01", 60, None, None, "DKK"),  # mangler kurs
    ("DK0060497719", "Pandora", "Ultimo", "2024-12-31", 340, 410, None, "DKK"),
]


def generer(sti: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Transaktioner"
    ws.append(KOLONNER)
    for raekke in RAEKKER:
        ws.append(raekke)
    wb.save(sti)
    print(f"Testdata gemt: {sti}")


if __name__ == "__main__":
    output = Path(__file__).parent / "eksempel_transaktioner.xlsx"
    generer(output)
