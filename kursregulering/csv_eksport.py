"""
Generering af CSV-fil klar til import i e-conomics kassekladde.

Fortegns-konvention (dansk bogføring, positivt beløb = debet, negativt = kredit):
- Balancekontoen (værdipapirer, som er en aktivkonto) er debet-normal.
  En gevinst ØGER værdien af beholdningen -> posteres som et positivt
  (debet) beløb. Et tab MINDSKER værdien -> negativt (kredit) beløb.
  Vi bruger derfor gevinst/tab-beløbet direkte, med fortegn, på balancekontoen.
- Resultatkontoen (kursregulering i resultatopgørelsen) får det MODSATTE
  fortegn af balancekontoen, så de to linjer altid summer til nul
  (bilaget balancerer). En gevinst bogføres dermed som kredit (indtægt
  stiger), et tab som debet (udgift stiger / indtægt falder).

Denne fortegns-konvention er en standardopsætning. Tjek den passer til jeres
egen kontoplan, og juster evt. i koden hvis jeres "kursregulering"-konto er
sat op omvendt.

Hver post (realiseret hhv. urealiseret regulering for ét papir) får sit eget
bilagsnummer og fylder to linjer, så det altid er tydeligt hvad der hører
sammen, og bilaget balancerer i sig selv.

Udbyttebetalinger (byg_udbytte_kassekladde_linjer) bogføres tilsvarende:
bruttoudbyttet krediteres resultatkontoen (indtægt), kildeskatten debiteres
en tilgodehavende-konto (dansk hhv. udenlandsk), og nettobeløbet debiteres
bankkontoen — de tre linjer summer altid til nul.
"""
from __future__ import annotations

import csv
import io
from dataclasses import dataclass
from datetime import date

import pandas as pd

from beregning import PapirBeregning
from udbytte import UdbytteResultat

TOLERANCE = 0.005  # under en halv øre anses for at være "ingen regulering"


@dataclass
class KassekladdeLinje:
    type: str
    bilagsnr: int
    dato: date
    konto: str
    beloeb: float
    tekst: str


def _format_beloeb_dansk(beloeb: float) -> str:
    """Formaterer et beløb som e-conomic/danske systemer forventer:
    punktum som tusindtalsseparator, komma som decimalseparator, fx
    "1.234,56". Beløbet rundes til 2 decimaler."""
    afrundet = round(beloeb, 2)
    tekst = f"{afrundet:,.2f}"  # engelsk format, fx "1,234.56"
    tekst = tekst.replace(",", "X").replace(".", ",").replace("X", ".")
    return tekst


def _format_dato_dansk(d: date) -> str:
    return d.strftime("%d-%m-%Y")


def byg_kassekladde_linjer(
    resultater: list[PapirBeregning],
    resultatkonto: str,
    balancekonto: str,
    bogfoeringsdato: date,
    bilagstype: str = "Finansbilag",
    start_bilagsnummer: int = 1,
) -> list[KassekladdeLinje]:
    """Bygger de rå kassekladde-linjer (før CSV-formatering) ud fra
    beregningsresultaterne. Springer poster over hvor beløbet er ~0, da de
    ikke har nogen resultatpåvirkning."""
    linjer: list[KassekladdeLinje] = []
    bilagsnr = start_bilagsnummer

    for r in resultater:
        for label, beloeb in (("realiseret", r.realiseret), ("urealiseret", r.urealiseret)):
            if abs(beloeb) < TOLERANCE:
                continue
            tekst = f"Kursregulering {r.papirnavn} – {label} gevinst/tab"
            # Balancelinje: samme fortegn som reguleringen (se modulets docstring)
            linjer.append(
                KassekladdeLinje(
                    type=bilagstype,
                    bilagsnr=bilagsnr,
                    dato=bogfoeringsdato,
                    konto=balancekonto,
                    beloeb=beloeb,
                    tekst=tekst,
                )
            )
            # Modpostering på resultatkontoen: modsat fortegn, så bilaget balancerer
            linjer.append(
                KassekladdeLinje(
                    type=bilagstype,
                    bilagsnr=bilagsnr,
                    dato=bogfoeringsdato,
                    konto=resultatkonto,
                    beloeb=-beloeb,
                    tekst=tekst,
                )
            )
            bilagsnr += 1

    return linjer


def byg_udbytte_kassekladde_linjer(
    resultater: list[UdbytteResultat],
    resultatkonto: str,
    bankkonto: str,
    dansk_skattekonto: str,
    udenlandsk_skattekonto: str,
    bilagstype: str = "Finansbilag",
    start_bilagsnummer: int = 1,
) -> list[KassekladdeLinje]:
    """Bygger kassekladde-linjer for udbyttebetalinger. Hver betaling får sit
    eget bilagsnummer med op til 3 linjer, der balancerer:
    - Resultatkonto: kredit for bruttoudbytte (indtægt)
    - Skattekonto (dansk eller udenlandsk): debit for kildeskat (tilgodehavende)
    - Bankkonto: debit for det modtagne nettobeløb
    Springer skattelinjen over hvis kildeskatten er ~0."""
    linjer: list[KassekladdeLinje] = []
    bilagsnr = start_bilagsnummer

    for r in resultater:
        dato = r.dato.date() if pd.notna(r.dato) else date.today()
        tekst = f"Udbytte {r.papirnavn} ({r.landnavn})"

        linjer.append(
            KassekladdeLinje(bilagstype, bilagsnr, dato, resultatkonto, -r.brutto_udbytte, tekst)
        )
        if abs(r.kildeskat) >= TOLERANCE:
            skattekonto = dansk_skattekonto if r.er_dansk else udenlandsk_skattekonto
            linjer.append(KassekladdeLinje(bilagstype, bilagsnr, dato, skattekonto, r.kildeskat, tekst))
        linjer.append(KassekladdeLinje(bilagstype, bilagsnr, dato, bankkonto, r.netto_udbytte, tekst))

        bilagsnr += 1

    return linjer


def linjer_til_dataframe(linjer: list[KassekladdeLinje]) -> pd.DataFrame:
    """Preview-tabel til visning i UI'en (læsevenlige tal, ikke danskformateret tekst)."""
    return pd.DataFrame(
        [
            {
                "Type": l.type,
                "Bilagsnr.": l.bilagsnr,
                "Dato": l.dato.strftime("%d-%m-%Y"),
                "Konto": l.konto,
                "Beløb": round(l.beloeb, 2),
                "Tekst": l.tekst,
            }
            for l in linjer
        ]
    )


def generer_csv(linjer: list[KassekladdeLinje]) -> str:
    """Genererer selve CSV-teksten: semikolon-separeret, dansk tal- og
    datoformat, som e-conomic kræver ved import."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";", lineterminator="\r\n")
    writer.writerow(["Type", "Bilagsnr.", "Dato", "Konto", "Beløb", "Tekst"])
    for l in linjer:
        writer.writerow(
            [
                l.type,
                l.bilagsnr,
                _format_dato_dansk(l.dato),
                l.konto,
                _format_beloeb_dansk(l.beloeb),
                l.tekst,
            ]
        )
    # ﻿ (BOM) sikrer at Excel/e-conomic læser de danske bogstaver (æøå) korrekt
    return "﻿" + buffer.getvalue()
