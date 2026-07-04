"""
Genererer en eksempel-Excel-fil med udbyttebetalinger.

Tallene for Novo Nordisk og Volvo B er hentet direkte fra et virkeligt
regneark, så beregningen kan afstemmes mod kendte facit-tal.

Kør scriptet med: python generer_udbytte_testdata.py
"""
import openpyxl
from pathlib import Path

KOLONNER = ["Papirnavn", "Landekode", "Dato", "Netto udbytte"]

RAEKKER = [
    ("Novo Nordisk", "DK", "2024-03-26", 18823.41),
    ("Volvo B", "SE", "2024-04-05", 49149.72),
    ("Taiwan Semiconductor", "US", "2024-05-15", 19489.99),
    # Advarsel: mangler betalingsdato (ikke en fejl, men bør tjekkes)
    ("Novo Nordisk", "DK", None, 6500.00),
    # Fejl: ukendt landekode — kan ikke finde en skattesats
    ("Ukendt A/S", "ZZ", "2024-06-01", 2000.00),
    # Fejl: mangler beløb
    ("Roche", "CH", "2024-07-01", None),
]


def generer(sti: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Udbytte"
    ws.append(KOLONNER)
    for raekke in RAEKKER:
        ws.append(raekke)
    wb.save(sti)
    print(f"Testdata gemt: {sti}")


if __name__ == "__main__":
    output = Path(__file__).parent / "eksempel_udbytte.xlsx"
    generer(output)
