"""
Validering af de standardiserede transaktionsdata (output fra parser.py).

Kører en række tjek pr. værdipapir og samler resultatet i en liste af
`ValideringsFund`, som UI'en kan vise som en tabel. Hvert fund har et
niveau: "Fejl" (blokerer beregning) eller "Advarsel" (blokerer ikke, men
bør tjekkes).

Denne fil rører IKKE ved Streamlit — den kan bruges og testes for sig selv.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

FEJL = "Fejl"
ADVARSEL = "Advarsel"
OK = "OK"

# Rækkefølge bruges til at afgøre "værste status" for et papir
_NIVEAU_RANG = {OK: 0, ADVARSEL: 1, FEJL: 2}


@dataclass
class ValideringsFund:
    papir_id: str
    papirnavn: str
    niveau: str  # Fejl / Advarsel
    kategori: str
    besked: str
    excel_raekker: list[int]


def _linjer_tekst(raekker: list[int]) -> str:
    if not raekker:
        return ""
    return "Excel-række " + ", ".join(str(r) for r in sorted(set(raekker)))


def _tjek_saldo(gruppe: pd.DataFrame) -> list[ValideringsFund]:
    """Primo antal + Tilgange antal - Afgange antal skal give Ultimo antal."""
    fund = []
    primo = gruppe[gruppe["type"] == "primo"]
    tilgang = gruppe[gruppe["type"] == "tilgang"]
    afgang = gruppe[gruppe["type"] == "afgang"]
    ultimo = gruppe[gruppe["type"] == "ultimo"]

    if ultimo.empty:
        return fund  # håndteres af _tjek_primo_ultimo_tilstedevaerelse

    primo_antal = primo["antal"].sum(skipna=True)
    tilgang_antal = tilgang["antal"].sum(skipna=True)
    afgang_antal = afgang["antal"].sum(skipna=True)
    ultimo_antal = ultimo["antal"].sum(skipna=True)

    forventet = primo_antal + tilgang_antal - afgang_antal
    if abs(forventet - ultimo_antal) > 1e-6:
        raekker = list(gruppe["excel_raekke"])
        fund.append(
            ValideringsFund(
                papir_id=gruppe["papir_id"].iloc[0],
                papirnavn=gruppe["papirnavn"].iloc[0],
                niveau=FEJL,
                kategori="Saldo-kontrol",
                besked=(
                    f"Primo ({primo_antal:g}) + Tilgange ({tilgang_antal:g}) - "
                    f"Afgange ({afgang_antal:g}) = {forventet:g}, men Ultimo antal er "
                    f"{ultimo_antal:g}. Differencen er {ultimo_antal - forventet:g} stk."
                ),
                excel_raekker=raekker,
            )
        )
    return fund


def _tjek_manglende_data(gruppe: pd.DataFrame) -> list[ValideringsFund]:
    """Tomme felter i Dato, Antal eller Kurs på linjer der ikke er Primo/Ultimo."""
    fund = []
    relevante = gruppe[~gruppe["type"].isin(["primo", "ultimo"])]
    for _, row in relevante.iterrows():
        manglende = []
        if pd.isna(row["dato"]):
            manglende.append("Dato")
        if pd.isna(row["antal"]):
            manglende.append("Antal")
        if pd.isna(row["kurs"]):
            manglende.append("Kurs")
        if manglende:
            fund.append(
                ValideringsFund(
                    papir_id=row["papir_id"],
                    papirnavn=row["papirnavn"],
                    niveau=FEJL,
                    kategori="Manglende data",
                    besked=(
                        f"{row['type'].capitalize()}-linje mangler: {', '.join(manglende)}."
                    ),
                    excel_raekker=[int(row["excel_raekke"])],
                )
            )
    return fund


def _tjek_negative_vaerdier(gruppe: pd.DataFrame) -> list[ValideringsFund]:
    """Negativt antal ved Tilgang, negativ kurs, eller kurs = 0."""
    fund = []
    for _, row in gruppe.iterrows():
        raekke = int(row["excel_raekke"])
        if row["type"] == "tilgang" and pd.notna(row["antal"]) and row["antal"] < 0:
            fund.append(
                ValideringsFund(
                    papir_id=row["papir_id"],
                    papirnavn=row["papirnavn"],
                    niveau=FEJL,
                    kategori="Urealistisk værdi",
                    besked=f"Negativt antal ({row['antal']:g}) ved Tilgang.",
                    excel_raekker=[raekke],
                )
            )
        if pd.notna(row["kurs"]) and row["kurs"] < 0:
            fund.append(
                ValideringsFund(
                    papir_id=row["papir_id"],
                    papirnavn=row["papirnavn"],
                    niveau=FEJL,
                    kategori="Urealistisk værdi",
                    besked=f"Negativ kurs ({row['kurs']:g}) på {row['type']}-linje.",
                    excel_raekker=[raekke],
                )
            )
        if pd.notna(row["kurs"]) and row["kurs"] == 0 and row["type"] in ("primo", "tilgang", "afgang", "ultimo"):
            fund.append(
                ValideringsFund(
                    papir_id=row["papir_id"],
                    papirnavn=row["papirnavn"],
                    niveau=ADVARSEL,
                    kategori="Urealistisk værdi",
                    besked=f"Kurs = 0 på {row['type']}-linje. Kontrollér om det er korrekt.",
                    excel_raekker=[raekke],
                )
            )
    return fund


def _tjek_dato_raekkefoelge(gruppe: pd.DataFrame) -> list[ValideringsFund]:
    """Afgangsdato før tilsvarende tilgangsdato kan indikere forkert FIFO-rækkefølge."""
    fund = []
    tilgange = gruppe[(gruppe["type"] == "tilgang") & gruppe["dato"].notna()]
    afgange = gruppe[(gruppe["type"] == "afgang") & gruppe["dato"].notna()]
    if tilgange.empty or afgange.empty:
        return fund

    tidligste_tilgang = tilgange["dato"].min()
    for _, row in afgange.iterrows():
        if row["dato"] < tidligste_tilgang:
            fund.append(
                ValideringsFund(
                    papir_id=row["papir_id"],
                    papirnavn=row["papirnavn"],
                    niveau=ADVARSEL,
                    kategori="Dato-rækkefølge",
                    besked=(
                        f"Afgang den {row['dato'].date()} ligger før den tidligste "
                        f"Tilgang ({tidligste_tilgang.date()}). Tjek at FIFO-rækkefølgen er korrekt."
                    ),
                    excel_raekker=[int(row["excel_raekke"])],
                )
            )
    return fund


def _tjek_dubletter(gruppe: pd.DataFrame) -> list[ValideringsFund]:
    """Identiske linjer (samme type, dato, antal, kurs) kan være indtastningsfejl."""
    fund = []
    noegle_kolonner = ["type", "dato", "antal", "kurs"]
    dubletter = gruppe[gruppe.duplicated(subset=noegle_kolonner, keep=False)]
    for _, row in dubletter.iterrows():
        fund.append(
            ValideringsFund(
                papir_id=row["papir_id"],
                papirnavn=row["papirnavn"],
                niveau=ADVARSEL,
                kategori="Mulig dublet",
                besked=(
                    f"Identisk linje findes flere gange ({row['type']}, "
                    f"{row['dato'].date() if pd.notna(row['dato']) else '?'}, "
                    f"antal {row['antal']:g}, kurs {row['kurs']:g}). Kontrollér for dobbelt-indtastning."
                ),
                excel_raekker=[int(row["excel_raekke"])],
            )
        )
    return fund


def _tjek_primo_ultimo_tilstedevaerelse(gruppe: pd.DataFrame) -> list[ValideringsFund]:
    """Et papir uden Ultimo kan ikke beregnes urealiseret for. Manglende Primo er OK
    (antages nyt køb i året)."""
    fund = []
    raekker = list(gruppe["excel_raekke"])
    if not (gruppe["type"] == "ultimo").any():
        fund.append(
            ValideringsFund(
                papir_id=gruppe["papir_id"].iloc[0],
                papirnavn=gruppe["papirnavn"].iloc[0],
                niveau=FEJL,
                kategori="Manglende Ultimo",
                besked="Ingen Ultimo-linje fundet. Kan ikke beregne urealiseret gevinst/tab.",
                excel_raekker=raekker,
            )
        )
    return fund


def _tjek_beloeb_konsistens(gruppe: pd.DataFrame) -> list[ValideringsFund]:
    """Bonus-tjek: hvis Beløb er angivet direkte i filen (ikke udregnet af os),
    og det afviger fra Antal × Kurs, kan der være fejl eller kurtage indregnet."""
    fund = []
    for _, row in gruppe.iterrows():
        if pd.isna(row["antal"]) or pd.isna(row["kurs"]) or pd.isna(row["beløb"]):
            continue
        forventet = row["antal"] * row["kurs"]
        if abs(forventet) > 0 and abs(row["beløb"] - forventet) / max(abs(forventet), 1) > 0.01:
            fund.append(
                ValideringsFund(
                    papir_id=row["papir_id"],
                    papirnavn=row["papirnavn"],
                    niveau=ADVARSEL,
                    kategori="Beløb stemmer ikke",
                    besked=(
                        f"Beløb ({row['beløb']:g}) afviger fra Antal × Kurs "
                        f"({forventet:g}) på {row['type']}-linje. Kan skyldes kurtage/gebyrer."
                    ),
                    excel_raekker=[int(row["excel_raekke"])],
                )
            )
    return fund


_ALLE_TJEK = [
    _tjek_saldo,
    _tjek_manglende_data,
    _tjek_negative_vaerdier,
    _tjek_dato_raekkefoelge,
    _tjek_dubletter,
    _tjek_primo_ultimo_tilstedevaerelse,
    _tjek_beloeb_konsistens,
]


def valider_transaktioner(data: pd.DataFrame) -> list[ValideringsFund]:
    """Kører alle valideringstjek pr. værdipapir og returnerer en samlet liste af fund."""
    alle_fund: list[ValideringsFund] = []
    for _, gruppe in data.groupby("papir_id", sort=False):
        for tjek in _ALLE_TJEK:
            alle_fund.extend(tjek(gruppe))
    return alle_fund


def opsummer_pr_papir(data: pd.DataFrame, fund: list[ValideringsFund]) -> pd.DataFrame:
    """Laver en oversigtstabel: ét papir pr. række, med værste status og antal fund."""
    rows = []
    for papir_id, gruppe in data.groupby("papir_id", sort=False):
        papir_fund = [f for f in fund if f.papir_id == papir_id]
        antal_fejl = sum(1 for f in papir_fund if f.niveau == FEJL)
        antal_advarsler = sum(1 for f in papir_fund if f.niveau == ADVARSEL)
        if antal_fejl:
            status = FEJL
        elif antal_advarsler:
            status = ADVARSEL
        else:
            status = OK
        rows.append(
            {
                "Papir": gruppe["papirnavn"].iloc[0],
                "ISIN": gruppe["isin"].iloc[0] or "",
                "Status": status,
                "Antal fejl": antal_fejl,
                "Antal advarsler": antal_advarsler,
            }
        )
    return pd.DataFrame(rows)


def har_fejl(fund: list[ValideringsFund]) -> bool:
    return any(f.niveau == FEJL for f in fund)


def fund_til_dataframe(fund: list[ValideringsFund]) -> pd.DataFrame:
    """Detaljeret fund-tabel til visning i UI'en."""
    rows = [
        {
            "Papir": f.papirnavn,
            "ISIN": f.papir_id if f.papir_id != f.papirnavn else "",
            "Status": f.niveau,
            "Kategori": f.kategori,
            "Besked": f.besked,
            "Placering": _linjer_tekst(f.excel_raekker),
        }
        for f in fund
    ]
    df = pd.DataFrame(rows)
    if df.empty:
        return df
    # Vis fejl før advarsler
    df["_sort"] = df["Status"].map(_NIVEAU_RANG)
    df = df.sort_values(["_sort", "Papir"], ascending=[False, True]).drop(columns="_sort")
    return df.reset_index(drop=True)
