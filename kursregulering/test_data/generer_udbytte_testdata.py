"""
Genererer eksempel-filer (Excel og CSV) med udbyttebetalinger.

Tallene for Novo Nordisk og Volvo B er hentet direkte fra et virkeligt
regneark, så beregningen kan afstemmes mod kendte facit-tal. Rækkerne
blander bevidst Netto- og Brutto-indtastning, så begge veje bliver testet.

Kør scriptet med: python generer_udbytte_testdata.py
"""
import csv
from pathlib import Path

import openpyxl

KOLONNER = ["Papirnavn", "Landekode", "Type", "Beløb", "Dato"]

RAEKKER = [
    ("Novo Nordisk", "DK", "Netto", 18823.41, "2024-03-26"),
    # Brutto-eksempel: samme betaling som ovenfor ville give, hvis man i
    # stedet kendte bruttobeløbet (57823,20) frem for nettobeløbet.
    ("Volvo B", "SE", "Brutto", 57823.20, "2024-04-05"),
    ("Taiwan Semiconductor", "US", "Netto", 19489.99, "2024-05-15"),
    # Advarsel: mangler betalingsdato (ikke en fejl, men bør tjekkes)
    ("Novo Nordisk", "DK", "Netto", 6500.00, None),
    # Fejl: ukendt landekode — kan ikke finde en skattesats
    ("Ukendt A/S", "ZZ", "Netto", 2000.00, "2024-06-01"),
    # Fejl: mangler beløb
    ("Roche", "CH", "Netto", None, "2024-07-01"),
]


def generer_excel(sti: Path) -> None:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Udbytte"
    ws.append(KOLONNER)
    for raekke in RAEKKER:
        ws.append(raekke)
    wb.save(sti)
    print(f"Testdata gemt: {sti}")


def generer_csv(sti: Path) -> None:
    with open(sti, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f, delimiter=";")
        writer.writerow(KOLONNER)
        for papirnavn, landekode, type_, beloeb, dato in RAEKKER:
            beloeb_tekst = "" if beloeb is None else f"{beloeb:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            dato_tekst = "" if dato is None else "-".join(reversed(dato.split("-")))  # ÅÅÅÅ-MM-DD -> DD-MM-ÅÅÅÅ
            writer.writerow([papirnavn, landekode, type_, beloeb_tekst, dato_tekst])
    print(f"Testdata gemt: {sti}")


if __name__ == "__main__":
    mappe = Path(__file__).parent
    generer_excel(mappe / "eksempel_udbytte.xlsx")
    generer_csv(mappe / "eksempel_udbytte.csv")
