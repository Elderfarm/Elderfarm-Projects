"""
Parser til indlæsning af Excel-fil med værdipapirtransaktioner.

Formålet er at læse en uploadet Excel-fil, genkende kolonnerne uanset
små navnevariationer (fx "Navn" vs. "Papirnavn"), og lave dataene om til
et standardiseret format, som resten af programmet (validering og
beregning) kan regne videre på.

Denne fil rører IKKE ved Streamlit — den kan bruges og testes helt for
sig selv.
"""
from __future__ import annotations

import datetime
import re
from dataclasses import dataclass, field

import pandas as pd

# Matcher datoer skrevet som ÅÅÅÅ-MM-DD eller ÅÅÅÅ/MM/DD (ISO), hvor
# rækkefølgen år-måned-dag er entydig og IKKE skal dag/måned-byttes om.
_ISO_DATO_MOENSTER = re.compile(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}")


def parse_enkelt_dato(vaerdi):
    """Fortolker én dato-værdi robust.

    Excel-datoer kan enten komme som rigtige dato-objekter (når cellen er
    formateret som dato) eller som tekst. Tekst kan være skrevet dansk
    (dag-måned-år, fx "31-12-2024") eller i ISO-format (år-måned-dag, fx
    "2024-12-31"). Pandas' `dayfirst`-parameter forvirrer desværre disse to
    formater, når hele kolonnen fortolkes under ét (dag og måned kan begge
    være ≤ 12), så vi afgør format pr. værdi i stedet.
    """
    if vaerdi is None or (isinstance(vaerdi, float) and pd.isna(vaerdi)):
        return pd.NaT
    if isinstance(vaerdi, (pd.Timestamp, datetime.datetime, datetime.date)):
        return pd.Timestamp(vaerdi)
    tekst = str(vaerdi).strip()
    if not tekst or tekst.lower() == "nan":
        return pd.NaT
    dayfirst = not bool(_ISO_DATO_MOENSTER.match(tekst))
    return pd.to_datetime(tekst, dayfirst=dayfirst, errors="coerce")

# Hvilke kolonnenavne (i småbogstaver, uden mellemrum i siderne) vi accepterer
# som synonymer for hvert standardfelt. Tilføj flere her, hvis en kundefil
# bruger andre betegnelser.
KOLONNE_SYNONYMER: dict[str, list[str]] = {
    "isin": ["isin"],
    "papirnavn": ["papirnavn", "navn", "værdipapir", "papir", "titel"],
    "type": ["type", "transaktionstype", "posteringstype"],
    "dato": ["dato", "transaktionsdato", "handelsdato"],
    "antal": ["antal", "stk", "stk.", "stykker"],
    "kurs": ["kurs", "pris", "kurs pr. stk", "pris pr. stk", "kurs pr stk"],
    "beløb": ["beløb", "beloeb", "værdi", "total", "value"],
    "valuta": ["valuta", "currency", "møntfod"],
}

# Felter som transaktionerne IKKE kan undværes uden (ISIN/papirnavn håndteres
# separat, da mindst ét af dem skal være til stede).
PAAKRAEVEDE_FELTER = ["type", "dato", "antal", "kurs"]

GYLDIGE_TYPER = {"primo", "tilgang", "afgang", "ultimo"}


@dataclass
class ParseResultat:
    """Samlet resultat af indlæsning: de standardiserede data plus info om
    hvordan kolonnerne blev genkendt, så brugeren kan gennemskue evt. fejl."""

    data: pd.DataFrame
    kolonne_mapping: dict[str, str]  # standardnavn -> kolonnenavn fundet i filen
    info: list[str] = field(default_factory=list)  # informationsbeskeder til UI
    kritiske_fejl: list[str] = field(default_factory=list)  # gør at vi slet ikke kan fortsætte

    @property
    def er_gyldig(self) -> bool:
        return len(self.kritiske_fejl) == 0


def _normaliser_header(navn: str) -> str:
    """Gør et kolonnenavn robust at sammenligne: små bogstaver, uden
    ekstra mellemrum og uden punktum."""
    return str(navn).strip().lower().replace(".", "").replace("  ", " ")


def genkend_kolonner(df: pd.DataFrame) -> tuple[dict[str, str], list[str]]:
    """Finder hvilken faktisk kolonne i df der svarer til hvert standardfelt.

    Returnerer (mapping, ugenkendte_kolonner). Mapping går fra standardnavn
    (fx "papirnavn") til det faktiske kolonnenavn i filen (fx "Navn").
    """
    normaliserede = {_normaliser_header(c): c for c in df.columns}
    mapping: dict[str, str] = {}

    for standardnavn, synonymer in KOLONNE_SYNONYMER.items():
        for synonym in synonymer:
            if synonym in normaliserede:
                mapping[standardnavn] = normaliserede[synonym]
                break

    genkendte_kolonner = set(mapping.values())
    ugenkendte = [c for c in df.columns if c not in genkendte_kolonner]
    return mapping, ugenkendte


def _lav_papir_id(row: pd.Series) -> str:
    """Nøglen vi grupperer transaktioner efter: ISIN hvis den findes,
    ellers papirnavnet. Sikrer at hvert værdipapir kan identificeres
    entydigt, selvom ISIN mangler for nogle papirer (fx nye køb).

    Forventer at 'isin' og 'papirnavn' allerede er normaliseret til enten
    en rigtig tekststreng eller tom streng "" (aldrig None/NaN) — se
    normaliseringen i indlaes_excel().
    """
    isin = row.get("isin", "")
    if isin:
        return isin
    return row.get("papirnavn", "")


def indlaes_excel(fil, ark: str | None = None) -> ParseResultat:
    """Indlæser en Excel-fil (path eller file-like objekt) og standardiserer
    kolonnerne. `ark` kan angive et specifikt arknavn, ellers bruges det
    første ark i filen.
    """
    try:
        if ark:
            raw = pd.read_excel(fil, sheet_name=ark, engine="openpyxl")
        else:
            raw = pd.read_excel(fil, sheet_name=0, engine="openpyxl")
    except Exception as e:  # noqa: BLE001 - vi vil vise fejlen pænt til brugeren
        return ParseResultat(
            data=pd.DataFrame(),
            kolonne_mapping={},
            kritiske_fejl=[f"Kunne ikke læse Excel-filen: {e}"],
        )

    # Fjern helt tomme rækker (fx tomme linjer nederst i arket)
    raw = raw.dropna(how="all").reset_index(drop=True)

    mapping, ugenkendte = genkend_kolonner(raw)
    info: list[str] = []
    kritiske_fejl: list[str] = []

    if "isin" not in mapping and "papirnavn" not in mapping:
        kritiske_fejl.append(
            "Kunne ikke finde en kolonne for ISIN eller Papirnavn/Navn. "
            "Mindst én af dem skal være til stede for at identificere værdipapirerne."
        )

    for felt in PAAKRAEVEDE_FELTER:
        if felt not in mapping:
            kritiske_fejl.append(
                f"Kunne ikke finde en kolonne for påkrævet felt: '{felt}'."
            )

    if kritiske_fejl:
        return ParseResultat(
            data=pd.DataFrame(), kolonne_mapping=mapping, info=info, kritiske_fejl=kritiske_fejl
        )

    # Byg det standardiserede datasæt med faste kolonnenavne
    std = pd.DataFrame()
    for standardnavn, kolonnenavn in mapping.items():
        std[standardnavn] = raw[kolonnenavn]

    if "isin" not in std.columns:
        std["isin"] = None
        info.append("Ingen ISIN-kolonne fundet — bruger kun Papirnavn til at identificere værdipapirer.")
    if "papirnavn" not in std.columns:
        std["papirnavn"] = std["isin"]
        info.append("Ingen Papirnavn-kolonne fundet — bruger ISIN som navn.")

    if "valuta" not in std.columns:
        std["valuta"] = "DKK"
        info.append("Ingen Valuta-kolonne fundet — antager DKK for alle linjer.")
    else:
        std["valuta"] = std["valuta"].fillna("DKK")

    # Gem det oprindelige rækkenummer (som i Excel, dvs. +2 for header og 1-index)
    std["excel_raekke"] = std.index + 2

    # Normaliser Type-teksten så "primo", " Primo ", "PRIMO" alle bliver "primo"
    std["type"] = std["type"].astype(str).str.strip().str.lower()
    ukendte_typer = sorted(set(std["type"]) - GYLDIGE_TYPER - {"nan"})
    if ukendte_typer:
        info.append(
            "Følgende værdier i Type-kolonnen genkendes ikke som "
            f"Primo/Tilgang/Afgang/Ultimo: {', '.join(ukendte_typer)}."
        )

    # Datoer og tal konverteres til rigtige typer. Fejl i konverteringen
    # bliver til NaT/NaN, som valideringsmodulet efterfølgende fanger som
    # "manglende data" i stedet for at vælte hele programmet.
    std["dato"] = std["dato"].apply(parse_enkelt_dato)
    std["antal"] = pd.to_numeric(std["antal"], errors="coerce")
    std["kurs"] = pd.to_numeric(std["kurs"], errors="coerce")

    if "beløb" not in std.columns:
        std["beløb"] = pd.NA
    std["beløb"] = pd.to_numeric(std["beløb"], errors="coerce")

    # Udregn Beløb hvor det mangler, men Antal og Kurs findes
    kan_udregnes = std["beløb"].isna() & std["antal"].notna() & std["kurs"].notna()
    std.loc[kan_udregnes, "beløb"] = std.loc[kan_udregnes, "antal"] * std.loc[kan_udregnes, "kurs"]

    # ISIN og papirnavn som rene strenge (nemmere at sammenligne/gruppere).
    # Manglende værdi bliver ALTID til "" (aldrig None/NaN) — det undgår at
    # rode med pandas' streng-datatype, hvor et manglende felt ellers kan
    # ende som et "sandt" NaN-flydetal (som er "truthy" i Python og derfor
    # nemt giver fejl i `x or standardværdi`-udtryk andre steder i koden).
    std["isin"] = std["isin"].apply(lambda v: "" if pd.isna(v) else str(v).strip())
    std["papirnavn"] = std["papirnavn"].apply(lambda v: "" if pd.isna(v) else str(v).strip())

    std["papir_id"] = std.apply(_lav_papir_id, axis=1)

    if ugenkendte:
        info.append(
            "Følgende kolonner i filen blev ikke brugt (ignoreret): "
            + ", ".join(str(c) for c in ugenkendte)
        )

    return ParseResultat(data=std, kolonne_mapping=mapping, info=info, kritiske_fejl=kritiske_fejl)
