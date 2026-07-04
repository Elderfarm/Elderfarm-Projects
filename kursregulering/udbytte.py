"""
Beregning af udbytte: bruttoudbytte og kildeskat pr. udbyttebetaling.

MODEL (bevidst forenklet udgave af den mere avancerede skabelon, hvor
udenlandsk kildeskat også opdeles i "tilbagesøges via selvangivelse" og
"tilbagesøges via banken" efter dobbeltbeskatningsoverenskomstens
maks-sats pr. land — den opdeling er tax-teknisk speciel og er bevidst
IKKE med her):

- For hver betaling kender man ÉT beløb — enten NETTO (det der reelt blev
  indsat på bankkontoen) eller BRUTTO (det fulde udbytte før skat). Man
  angiver selv hvilken af de to man har, pr. linje.
- Det andet beløb findes ved at bruge den kendte nettoprocent for
  kildelandet (se LANDE_NETTOPROCENT nedenfor): Brutto = Netto / nettoprocent,
  eller Netto = Brutto × nettoprocent.
- Kildeskat = Bruttoudbytte − Nettoudbytte.
- Beløbene opdeles i "Dansk" og "Udenlandsk" afhængigt af kildelandet, da de
  bogføres på hver sin tilgodehavende-konto (se csv_eksport.py). Den danske
  konto er dét, der kan tilbagesøges/modregnes i Danmark (hjemlandet).

Data kan komme fra to steder, som begge ender i samme standardiserede
tabel (papirnavn, dato, landekode, landnavn, beloeb, beloeb_type, raekke):
- `indlaes_udbytte_fil()` — upload af en Excel- eller CSV-fil
- `fra_indtastningstabel()` — brugerens direkte indtastning i en tabel i UI'en

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

NAVN_TIL_LANDEKODE: dict[str, str] = {navn.upper(): kode for kode, navn in LANDE_NAVNE.items()}

GYLDIGE_BELOEBSTYPER = {"netto", "brutto"}

KOLONNE_SYNONYMER: dict[str, list[str]] = {
    "papirnavn": ["papirnavn", "navn", "værdipapir", "papir", "titel"],
    "dato": ["dato", "betalingsdato", "handelsdato"],
    "land": ["land", "lande"],
    "landekode": ["landekode", "land-kode", "kode"],
    "isin": ["isin"],
    "type": ["type", "beløbstype", "netto/brutto", "brutto/netto"],
    "beloeb_netto": ["netto udbytte", "nettoudbytte", "netto"],
    "beloeb_brutto": ["brutto udbytte", "bruttoudbytte", "brutto"],
    "beloeb_generisk": ["beløb", "modtaget beløb", "udbytte"],
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
    # ﻿ er en BOM, som ofte ligger forrest i CSV-filer gemt fra Excel —
    # den skal ikke være en del af det første kolonnenavn.
    return str(navn).strip().lstrip("﻿").lower().replace(".", "")


def _genkend_kolonner(df: pd.DataFrame) -> dict[str, str]:
    normaliserede = {_normaliser_header(c): c for c in df.columns}
    mapping: dict[str, str] = {}
    for standardnavn, synonymer in KOLONNE_SYNONYMER.items():
        for synonym in synonymer:
            if synonym in normaliserede:
                mapping[standardnavn] = normaliserede[synonym]
                break
    return mapping


def _udled_landekode(land_raa: object, isin_raa: object) -> str:
    """Bruger Landekode/Land-værdien hvis den er udfyldt (accepterer både
    en 2-bogstavs-kode og et fuldt landenavn), ellers de to første
    bogstaver af ISIN-nummeret."""
    if pd.notna(land_raa) and str(land_raa).strip():
        tekst = str(land_raa).strip().upper()
        if tekst in NAVN_TIL_LANDEKODE:
            return NAVN_TIL_LANDEKODE[tekst]
        return tekst
    if pd.notna(isin_raa) and len(str(isin_raa).strip()) >= 2:
        return re.sub(r"[^A-Z]", "", str(isin_raa).strip().upper())[:2]
    return ""


def _parse_beloeb_vaerdi(vaerdi: object) -> float | None:
    """Fortolker et beløb robust, uanset om det er et tal (fra Excel) eller
    tekst i dansk eller engelsk talformat (fra en CSV-fil), fx "18.823,41",
    "18823,41" eller "18823.41"."""
    if vaerdi is None:
        return None
    if isinstance(vaerdi, (int, float)):
        return None if pd.isna(vaerdi) else float(vaerdi)
    tekst = str(vaerdi).strip().replace(" ", "").replace("kr.", "").replace("kr", "")
    if not tekst or tekst.lower() == "nan":
        return None
    if "," in tekst and "." in tekst:
        tekst = tekst.replace(".", "").replace(",", ".")
    elif "," in tekst:
        tekst = tekst.replace(",", ".")
    try:
        return float(tekst)
    except ValueError:
        return None


def _normaliser_beloebstype(vaerdi: object, standard: str) -> str:
    """Tomt/ukendt -> brug standardtypen (udledt af hvilken beløbskolonne der
    blev fundet). En udfyldt værdi normaliseres til 'netto'/'brutto' hvis
    den kan genkendes, ellers returneres den rå (små bogstaver) tekst, så
    valideringen kan flage den som en fejl."""
    if pd.isna(vaerdi) or not str(vaerdi).strip():
        return standard
    tekst = str(vaerdi).strip().lower()
    if tekst.startswith("net"):
        return "netto"
    if tekst.startswith("brut"):
        return "brutto"
    return tekst


def indlaes_udbytte_fil(fil, filnavn: str, ark: str | None = None) -> UdbytteParseResultat:
    """Indlæser en Excel- eller CSV-fil med udbyttebetalinger og
    standardiserer kolonnerne. Filtype afgøres af filnavnets endelse."""
    er_csv = filnavn.lower().endswith(".csv")
    try:
        if er_csv:
            raw = pd.read_csv(fil, sep=None, engine="python")
        else:
            raw = pd.read_excel(fil, sheet_name=ark or 0, engine="openpyxl")
    except Exception as e:  # noqa: BLE001
        filtype = "CSV-filen" if er_csv else "Excel-filen"
        return UdbytteParseResultat(pd.DataFrame(), {}, [], [f"Kunne ikke læse {filtype}: {e}"])

    raw = raw.dropna(how="all").reset_index(drop=True)
    mapping = _genkend_kolonner(raw)
    info: list[str] = []
    kritiske_fejl: list[str] = []

    if "papirnavn" not in mapping:
        kritiske_fejl.append("Kunne ikke finde en kolonne med papirnavn (fx 'Papirnavn' eller 'Navn').")

    beloeb_kolonne = None
    standard_type = "netto"
    for felt, type_ in (("beloeb_netto", "netto"), ("beloeb_brutto", "brutto"), ("beloeb_generisk", "netto")):
        if felt in mapping:
            beloeb_kolonne = mapping[felt]
            standard_type = type_
            break
    if beloeb_kolonne is None:
        kritiske_fejl.append(
            "Kunne ikke finde en kolonne med et beløb (fx 'Netto udbytte', 'Brutto udbytte' eller 'Beløb')."
        )

    if "landekode" not in mapping and "land" not in mapping and "isin" not in mapping:
        kritiske_fejl.append("Kunne ikke finde en kolonne med land, landekode eller ISIN.")

    if kritiske_fejl:
        return UdbytteParseResultat(pd.DataFrame(), mapping, info, kritiske_fejl)

    std = pd.DataFrame(index=raw.index)
    std["papirnavn"] = raw[mapping["papirnavn"]].apply(lambda v: "" if pd.isna(v) else str(v).strip())

    if "dato" not in mapping:
        std["dato"] = pd.NaT
        info.append("Ingen dato-kolonne fundet — betalingsdato vises tom.")
    else:
        std["dato"] = raw[mapping["dato"]].apply(parse_enkelt_dato)

    land_raa = raw[mapping["land"]] if "land" in mapping else (raw[mapping["landekode"]] if "landekode" in mapping else pd.Series([None] * len(raw)))
    isin_raa = raw[mapping["isin"]] if "isin" in mapping else pd.Series([None] * len(raw))
    std["landekode"] = [
        _udled_landekode(land_raa.iloc[i], isin_raa.iloc[i]) for i in range(len(raw))
    ]
    std["landnavn"] = std["landekode"].map(LANDE_NAVNE).fillna(std["landekode"])

    std["beloeb"] = raw[beloeb_kolonne].apply(_parse_beloeb_vaerdi)
    if "type" in mapping:
        std["beloeb_type"] = raw[mapping["type"]].apply(lambda v: _normaliser_beloebstype(v, standard_type))
    else:
        std["beloeb_type"] = standard_type

    std["raekke"] = std.index + 2

    return UdbytteParseResultat(data=std, kolonne_mapping=mapping, info=info, kritiske_fejl=kritiske_fejl)


def eksempel_indtastningsraekke() -> pd.DataFrame:
    """Én udfyldt eksempel-række til at forudfylde indtastningstabellen i
    UI'en, så brugeren kan se formatet og bare redigere/tilføje flere."""
    return pd.DataFrame(
        [{"Papir": "Novo Nordisk", "Land": "Danmark", "Type": "Netto", "Beløb (kr.)": 18823.41, "Dato": pd.Timestamp("2024-03-26")}]
    )


def til_indtastningstabel(std: pd.DataFrame) -> pd.DataFrame:
    """Omvendt af fra_indtastningstabel(): bygger den redigerbare tabel (til
    st.data_editor) ud fra det standardiserede format. Bruges når en
    upload skal fortolkes ind i indtastningstabellen, så bruger kan se og
    rette i den, før der beregnes."""
    return pd.DataFrame(
        {
            "Papir": std["papirnavn"],
            "Land": std["landnavn"],
            "Type": std["beloeb_type"].map({"netto": "Netto", "brutto": "Brutto"}).fillna(std["beloeb_type"]),
            "Beløb (kr.)": std["beloeb"],
            "Dato": std["dato"],
        }
    )


def fra_indtastningstabel(tabel: pd.DataFrame) -> pd.DataFrame:
    """Konverterer brugerens direkte indtastning (fra st.data_editor, med
    kolonnerne Papir/Land/Type/Beløb (kr.)/Dato) til samme standardiserede
    format som indlaes_udbytte_fil() returnerer."""
    std = pd.DataFrame(index=tabel.index)
    std["papirnavn"] = tabel["Papir"].apply(lambda v: "" if pd.isna(v) else str(v).strip())
    std["dato"] = tabel["Dato"].apply(parse_enkelt_dato)
    std["landekode"] = tabel["Land"].apply(lambda v: _udled_landekode(v, None))
    std["landnavn"] = std["landekode"].map(LANDE_NAVNE).fillna(std["landekode"])
    std["beloeb"] = tabel["Beløb (kr.)"].apply(_parse_beloeb_vaerdi)
    std["beloeb_type"] = tabel["Type"].apply(lambda v: _normaliser_beloebstype(v, "netto"))
    std["raekke"] = range(1, len(tabel) + 1)
    return std


# ---------------------------------------------------------------------------
# Validering
# ---------------------------------------------------------------------------

FEJL = "Fejl"
ADVARSEL = "Advarsel"


@dataclass
class UdbytteFund:
    raekke: int
    papirnavn: str
    niveau: str
    besked: str


def valider_udbytte(data: pd.DataFrame) -> list[UdbytteFund]:
    fund: list[UdbytteFund] = []
    for _, row in data.iterrows():
        raekke = int(row["raekke"])
        if not row["papirnavn"]:
            fund.append(UdbytteFund(raekke, row["papirnavn"], FEJL, "Mangler papirnavn."))
        if pd.isna(row["beloeb"]):
            fund.append(UdbytteFund(raekke, row["papirnavn"], FEJL, "Mangler beløb."))
        elif row["beloeb"] <= 0:
            fund.append(UdbytteFund(raekke, row["papirnavn"], FEJL, "Beløbet skal være positivt."))
        if row["beloeb_type"] not in GYLDIGE_BELOEBSTYPER:
            fund.append(
                UdbytteFund(
                    raekke, row["papirnavn"], FEJL,
                    f"Ukendt beløbstype '{row['beloeb_type']}' — skal være Netto eller Brutto.",
                )
            )
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
    rows = [{"Række": f.raekke, "Papir": f.papirnavn, "Status": f.niveau, "Besked": f.besked} for f in fund]
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
    nettoprocent = LANDE_NETTOPROCENT[landekode] / 100
    beloeb = float(row["beloeb"])
    if row["beloeb_type"] == "brutto":
        brutto = beloeb
        netto = brutto * nettoprocent
    else:
        netto = beloeb
        brutto = netto / nettoprocent
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
                "Nettoudbytte": round(r.netto_udbytte, 2),
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
