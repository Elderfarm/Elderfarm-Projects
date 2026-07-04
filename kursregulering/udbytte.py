"""
Beregning af udbytte: bruttoudbytte og kildeskat pr. udbyttebetaling.

MODEL (bevidst forenklet udgave af den mere avancerede skabelon, hvor
udenlandsk kildeskat også opdeles i "tilbagesøges via selvangivelse" og
"tilbagesøges via banken" efter dobbeltbeskatningsoverenskomstens
maks-sats pr. land — den opdeling er tax-teknisk speciel og er bevidst
IKKE med her):

- I banken modtager selskabet et NETTOBELØB (Netto udbytte) — det er det
  beløb, der reelt bliver indsat på bankkontoen.
- Bruttoudbytte findes ved at "gange nettobeløbet op" med den kendte
  nettoprocent for kildelandet (se LANDE_NETTOPROCENT nedenfor). Fx hvis et
  land tilbageholder 22% i kildeskat, er nettoprocenten 78%, og
  Bruttoudbytte = Nettoudbytte / 0,78.
- Kildeskat = Bruttoudbytte − Nettoudbytte.
- Beløbene opdeles i "Dansk" og "Udenlandsk" afhængigt af kildelandet, da de
  bogføres på hver sin tilgodehavende-konto (se csv_eksport.py).

Denne fil rører IKKE ved Streamlit — den kan bruges og testes for sig selv,
ligesom parser.py/validering.py/beregning.py for kursregulering.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from parser import parse_enkelt_dato  # samme robuste datofortolkning som kursregulering bruger

# Nettoprocent pr. land = hvor stor en andel af bruttoudbyttet selskabet reelt
# modtager, efter at kildelandet har trukket sin udbytteskat. Baseret på de
# almindelige dobbeltbeskatningsoverenskomst-satser, Danmark har med landet.
# Justér tallene her, hvis I har en anden aftale, eller tilføj flere lande.
LANDE_NETTOPROCENT: dict[str, float] = {
    "US": 85, "CH": 65, "FR": 75, "ES": 81, "DE": 73.625, "GB": 100,
    "JP": 100 - 15.32, "BE": 85, "IT": 74, "IE": 75, "PO": 85, "CA": 85,
    "SE": 85, "FI": 65, "NO": 75, "SG": 100, "TH": 90, "KI": 90, "NL": 85,
    "TW": 90, "DK": 78, "LU": 85, "IL": 75, "AUD": 70,
}

LANDE_NAVNE: dict[str, str] = {
    "US": "USA", "CH": "Schweiz", "FR": "Frankrig", "ES": "Spanien", "DE": "Tyskland",
    "GB": "Storbritannien", "JP": "Japan", "BE": "Belgien", "IT": "Italien", "IE": "Irland",
    "PO": "Polen", "CA": "Canada", "SE": "Sverige", "FI": "Finland", "NO": "Norge",
    "SG": "Singapore", "TH": "Thailand", "KI": "Kina", "NL": "Holland", "TW": "Taiwan",
    "DK": "Danmark", "LU": "Luxembourg", "IL": "Israel", "AUD": "Australien",
}

KOLONNE_SYNONYMER: dict[str, list[str]] = {
    "papirnavn": ["papirnavn", "navn", "værdipapir", "papir", "titel"],
    "dato": ["dato", "betalingsdato", "handelsdato"],
    "land": ["land", "lande"],
    "landekode": ["landekode", "land-kode", "kode"],
    "isin": ["isin"],
    "netto_udbytte": ["netto udbytte", "nettoudbytte", "netto", "beløb", "modtaget beløb"],
}


@dataclass
class UdbytteParseResultat:
    data: pd.DataFrame
    kolonne_mapping: dict[str, str]
    info: list[str]
    kritiske_fejl: list[str]

    @property
    def er_gyldig(self) -> bool:
        return len(self.kritiske_fejl) == 0


def _normaliser_header(navn: str) -> str:
    return str(navn).strip().lower().replace(".", "")


def _genkend_kolonner(df: pd.DataFrame) -> dict[str, str]:
    normaliserede = {_normaliser_header(c): c for c in df.columns}
    mapping: dict[str, str] = {}
    for standardnavn, synonymer in KOLONNE_SYNONYMER.items():
        for synonym in synonymer:
            if synonym in normaliserede:
                mapping[standardnavn] = normaliserede[synonym]
                break
    return mapping


def _udled_landekode(raekke: pd.Series) -> str:
    """Bruger Landekode/Land-kolonnen hvis den er udfyldt, ellers de to
    første bogstaver af ISIN-nummeret (samme konvention som skabelonen)."""
    for felt in ("landekode", "land"):
        vaerdi = raekke.get(felt)
        if pd.notna(vaerdi) and str(vaerdi).strip():
            kode = str(vaerdi).strip().upper()
            # Hvis "Land" indeholder et fuldt landenavn i stedet for en kode
            for kode_kandidat, navn in LANDE_NAVNE.items():
                if navn.upper() == kode:
                    return kode_kandidat
            return kode
    isin = raekke.get("isin")
    if pd.notna(isin) and len(str(isin).strip()) >= 2:
        return re.sub(r"[^A-Z]", "", str(isin).strip().upper())[:2]
    return ""


def indlaes_udbytte_excel(fil, ark: str | None = None) -> UdbytteParseResultat:
    """Indlæser en Excel-fil med udbyttebetalinger og standardiserer kolonnerne."""
    try:
        raw = pd.read_excel(fil, sheet_name=ark or 0, engine="openpyxl")
    except Exception as e:  # noqa: BLE001
        return UdbytteParseResultat(pd.DataFrame(), {}, [], [f"Kunne ikke læse Excel-filen: {e}"])

    raw = raw.dropna(how="all").reset_index(drop=True)
    mapping = _genkend_kolonner(raw)
    info: list[str] = []
    kritiske_fejl: list[str] = []

    if "papirnavn" not in mapping:
        kritiske_fejl.append("Kunne ikke finde en kolonne med papirnavn (fx 'Papirnavn' eller 'Navn').")
    if "netto_udbytte" not in mapping:
        kritiske_fejl.append("Kunne ikke finde en kolonne med det modtagne beløb (fx 'Netto udbytte').")
    if "landekode" not in mapping and "land" not in mapping and "isin" not in mapping:
        kritiske_fejl.append("Kunne ikke finde en kolonne med land, landekode eller ISIN.")

    if kritiske_fejl:
        return UdbytteParseResultat(pd.DataFrame(), mapping, info, kritiske_fejl)

    std = pd.DataFrame()
    for standardnavn, kolonnenavn in mapping.items():
        std[standardnavn] = raw[kolonnenavn]

    if "dato" not in std.columns:
        std["dato"] = pd.NaT
        info.append("Ingen dato-kolonne fundet — betalingsdato vises tom.")
    else:
        std["dato"] = std["dato"].apply(parse_enkelt_dato)

    std["papirnavn"] = std["papirnavn"].apply(lambda v: "" if pd.isna(v) else str(v).strip())
    std["netto_udbytte"] = pd.to_numeric(std["netto_udbytte"], errors="coerce")
    std["excel_raekke"] = std.index + 2
    std["landekode"] = std.apply(_udled_landekode, axis=1)
    std["landnavn"] = std["landekode"].map(LANDE_NAVNE).fillna(std["landekode"])

    return UdbytteParseResultat(data=std, kolonne_mapping=mapping, info=info, kritiske_fejl=kritiske_fejl)


# ---------------------------------------------------------------------------
# Validering
# ---------------------------------------------------------------------------

FEJL = "Fejl"
ADVARSEL = "Advarsel"


@dataclass
class UdbytteFund:
    excel_raekke: int
    papirnavn: str
    niveau: str
    besked: str


def valider_udbytte(data: pd.DataFrame) -> list[UdbytteFund]:
    fund: list[UdbytteFund] = []
    for _, row in data.iterrows():
        raekke = int(row["excel_raekke"])
        if not row["papirnavn"]:
            fund.append(UdbytteFund(raekke, row["papirnavn"], FEJL, "Mangler papirnavn."))
        if pd.isna(row["netto_udbytte"]):
            fund.append(UdbytteFund(raekke, row["papirnavn"], FEJL, "Mangler det modtagne beløb."))
        elif row["netto_udbytte"] <= 0:
            fund.append(UdbytteFund(raekke, row["papirnavn"], FEJL, "Beløbet skal være positivt."))
        if not row["landekode"]:
            fund.append(UdbytteFund(raekke, row["papirnavn"], FEJL, "Mangler land/landekode/ISIN — kan ikke finde skattesats."))
        elif row["landekode"] not in LANDE_NETTOPROCENT:
            fund.append(
                UdbytteFund(
                    raekke, row["papirnavn"], FEJL,
                    f"Kender ikke skattesatsen for landekoden '{row['landekode']}'. "
                    "Ret landekoden, eller tilføj landet i LANDE_NETTOPROCENT i udbytte.py.",
                )
            )
        if pd.isna(row["dato"]):
            fund.append(UdbytteFund(raekke, row["papirnavn"], ADVARSEL, "Mangler betalingsdato."))
    return fund


def har_fejl(fund: list[UdbytteFund]) -> bool:
    return any(f.niveau == FEJL for f in fund)


def fund_til_dataframe(fund: list[UdbytteFund]) -> pd.DataFrame:
    if not fund:
        return pd.DataFrame()
    rows = [{"Excel-række": f.excel_raekke, "Papir": f.papirnavn, "Status": f.niveau, "Besked": f.besked} for f in fund]
    df = pd.DataFrame(rows)
    df["_sort"] = df["Status"].map({FEJL: 0, ADVARSEL: 1})
    return df.sort_values("_sort").drop(columns="_sort").reset_index(drop=True)


# ---------------------------------------------------------------------------
# Beregning
# ---------------------------------------------------------------------------


@dataclass
class UdbytteResultat:
    papirnavn: str
    dato: object
    landekode: str
    landnavn: str
    er_dansk: bool
    netto_udbytte: float
    brutto_udbytte: float
    kildeskat: float


def beregn_udbytte_linje(row: pd.Series) -> UdbytteResultat:
    landekode = row["landekode"]
    nettoprocent = LANDE_NETTOPROCENT[landekode]
    netto = float(row["netto_udbytte"])
    brutto = netto / (nettoprocent / 100)
    kildeskat = brutto - netto
    return UdbytteResultat(
        papirnavn=row["papirnavn"],
        dato=row["dato"],
        landekode=landekode,
        landnavn=row["landnavn"],
        er_dansk=(landekode == "DK"),
        netto_udbytte=netto,
        brutto_udbytte=brutto,
        kildeskat=kildeskat,
    )


def beregn_alle_udbytter(data: pd.DataFrame) -> list[UdbytteResultat]:
    """Beregner alle udbyttelinjer. Bør kun kaldes når valider_udbytte() ikke
    har fundet nogen 'Fejl'."""
    return [beregn_udbytte_linje(row) for _, row in data.iterrows()]


def resultater_til_dataframe(resultater: list[UdbytteResultat]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "Papir": r.papirnavn,
                "Dato": r.dato.date() if pd.notna(r.dato) else None,
                "Land": r.landnavn,
                "Modtaget (netto)": round(r.netto_udbytte, 2),
                "Bruttoudbytte": round(r.brutto_udbytte, 2),
                "Kildeskat": round(r.kildeskat, 2),
            }
            for r in resultater
        ]
    )


def opsummering(resultater: list[UdbytteResultat]) -> dict[str, float]:
    """Samlet total til overbliksvisning: dansk/udenlandsk brutto og kildeskat."""
    dansk = [r for r in resultater if r.er_dansk]
    udenlandsk = [r for r in resultater if not r.er_dansk]
    return {
        "dansk_brutto": sum(r.brutto_udbytte for r in dansk),
        "dansk_kildeskat": sum(r.kildeskat for r in dansk),
        "udenlandsk_brutto": sum(r.brutto_udbytte for r in udenlandsk),
        "udenlandsk_kildeskat": sum(r.kildeskat for r in udenlandsk),
        "netto_i_alt": sum(r.netto_udbytte for r in resultater),
    }
