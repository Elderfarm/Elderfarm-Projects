"""
Beregning af realiseret og urealiseret kursgevinst/-tab efter LAGERPRINCIPPET.

VIGTIGT — sådan virker lagerprincippet (modsat realisationsprincippet):

- `Primo kurs` er IKKE den oprindelige anskaffelsessum. Det er sidste års
  `Ultimo kurs`, altså markedsværdien ved forrige årsskifte. Den værdi er
  allerede blevet beskattet én gang (sidste år). Så "kostbasis" for
  primo-beholdningen i ÅRETS regulering er primo-kursen — ikke hvad
  aktierne oprindeligt blev købt for.
- Tilgange i året har basis = den faktiske købspris, da de ikke tidligere
  har været lagerbeskattet.
- Der beskattes hvert år, uanset om papiret sælges eller ej.

For hvert værdipapir deler vi årets samlede regulering op i to dele:

1. REALISERET: den del af reguleringen der vedrører stykker solgt i året.
   Vi bruger FIFO til at afgøre om et solgt stykke stammer fra
   primo-beholdningen eller fra en tilgang i året (primo-beholdningen
   anses altid for anskaffet før årets tilgange, uanset de enkelte
   transaktionsdatoer for afgange).
2. UREALISERET: den del der vedrører beholdning, der stadig er ejet ved
   ultimo, opgjort som ultimo-værdi minus den tilsvarende basis.

Denne fil er bevidst holdt fri af pandas/Streamlit-afhængigheder i selve
beregningskernen (`beregn_for_papir`), så den er let at skrive unit-tests for.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd

TOLERANCE = 1e-6


@dataclass
class Tilgangslot:
    """Én 'portion' af beholdningen med sin egen kostpris — enten resten af
    primo-beholdningen, eller (resten af) én bestemt tilgang i året."""

    kilde: str  # "primo" eller "tilgang"
    antal: float
    kurs: float
    dato: date | None = None


@dataclass
class PapirBeregning:
    """Samlet resultat af beregningen for ét værdipapir."""

    papir_id: str
    papirnavn: str
    isin: str

    primo_antal: float
    primo_kurs: float
    primo_vaerdi: float

    tilgang_antal: float
    tilgang_beloeb: float

    afgang_antal: float
    afgang_beloeb: float

    ultimo_antal: float
    ultimo_kurs: float
    ultimo_vaerdi: float

    kostbasis_solgt: float  # basis for de solgte stk (til kontrol/gennemsigtighed)
    kostbasis_resterende: float  # basis for beholdningen ved ultimo

    realiseret: float
    urealiseret: float

    kontrolsum_diff: float = 0.0  # bør altid være ~0 — se _kontroller()
    resterende_lots: list[Tilgangslot] = field(default_factory=list)

    @property
    def total(self) -> float:
        return self.realiseret + self.urealiseret


def _vaegtet_linje(gruppe: pd.DataFrame, type_navn: str) -> tuple[float, float, float]:
    """Summerer antal og beløb for en given linjetype (fx 'primo'), og
    udregner en beløbsvægtet gennemsnitskurs. Returnerer (antal, beløb, kurs).
    Håndterer også det (usædvanlige) tilfælde at der er flere linjer af
    samme type for samme papir."""
    linjer = gruppe[gruppe["type"] == type_navn]
    if linjer.empty:
        return 0.0, 0.0, 0.0
    antal = float(linjer["antal"].sum())
    beloeb = float(linjer["beløb"].sum())
    kurs = beloeb / antal if antal else 0.0
    return antal, beloeb, kurs


def _byg_tilgangslots(gruppe: pd.DataFrame) -> list[Tilgangslot]:
    """Én lot pr. Tilgang-linje, sorteret efter dato (ældste først), så
    FIFO-rækkefølgen er korrekt. Linjer uden dato sorteres sidst."""
    tilgange = gruppe[gruppe["type"] == "tilgang"].copy()
    tilgange = tilgange.sort_values(
        by="dato", na_position="last", kind="stable"
    )
    lots = []
    for _, row in tilgange.iterrows():
        dato = row["dato"].date() if pd.notna(row["dato"]) else None
        lots.append(Tilgangslot(kilde="tilgang", antal=float(row["antal"]), kurs=float(row["kurs"]), dato=dato))
    return lots


def _fordel_fifo(
    primo_antal: float,
    primo_kurs: float,
    tilgangslots: list[Tilgangslot],
    afgang_antal_total: float,
) -> tuple[float, float, list[Tilgangslot]]:
    """Fordeler årets samlede afgang på primo-beholdningen og tilgangene
    efter FIFO. Primo anses altid for anskaffet før årets tilgange.

    Returnerer (kostbasis for det solgte, resterende primo-antal,
    resterende tilgangslots efter salget).
    """
    at_saelge = afgang_antal_total

    solgt_fra_primo = min(at_saelge, primo_antal)
    resterende_primo_antal = primo_antal - solgt_fra_primo
    kostbasis_solgt = solgt_fra_primo * primo_kurs
    at_saelge -= solgt_fra_primo

    resterende_lots: list[Tilgangslot] = []
    for lot in tilgangslots:
        if at_saelge <= TOLERANCE:
            resterende_lots.append(lot)
            continue
        solgt_fra_lot = min(at_saelge, lot.antal)
        kostbasis_solgt += solgt_fra_lot * lot.kurs
        at_saelge -= solgt_fra_lot
        rest = lot.antal - solgt_fra_lot
        if rest > TOLERANCE:
            resterende_lots.append(Tilgangslot(kilde=lot.kilde, antal=rest, kurs=lot.kurs, dato=lot.dato))

    if at_saelge > TOLERANCE:
        raise ValueError(
            f"Kan ikke fordele afgang på beholdningen: {at_saelge:g} stk mangler basis "
            "(Primo + Tilgange er mindre end Afgange). Tjek saldo-valideringen for papiret."
        )

    return kostbasis_solgt, resterende_primo_antal, resterende_lots


def beregn_for_papir(gruppe: pd.DataFrame) -> PapirBeregning:
    """Beregner realiseret/urealiseret gevinst-tab for ét værdipapir.

    `gruppe` skal være de standardiserede transaktionsrækker (fra parser.py)
    for netop ét papir. Rejser ValueError hvis data ikke hænger sammen —
    UI'en bør derfor kun kalde denne funktion når valideringen ikke har
    fundet "Fejl" for papiret.
    """
    papir_id = gruppe["papir_id"].iloc[0]
    papirnavn = gruppe["papirnavn"].iloc[0]
    isin = gruppe["isin"].iloc[0]

    primo_antal, primo_vaerdi, primo_kurs = _vaegtet_linje(gruppe, "primo")
    tilgang_antal, tilgang_beloeb, _ = _vaegtet_linje(gruppe, "tilgang")
    afgang_antal, afgang_beloeb, _ = _vaegtet_linje(gruppe, "afgang")
    ultimo_antal, ultimo_vaerdi, ultimo_kurs = _vaegtet_linje(gruppe, "ultimo")

    if not (gruppe["type"] == "ultimo").any():
        raise ValueError(f"'{papirnavn}' mangler en Ultimo-linje — kan ikke beregnes.")

    tilgangslots = _byg_tilgangslots(gruppe)

    kostbasis_solgt, resterende_primo_antal, resterende_lots = _fordel_fifo(
        primo_antal, primo_kurs, tilgangslots, afgang_antal
    )

    kostbasis_resterende = resterende_primo_antal * primo_kurs + sum(
        lot.antal * lot.kurs for lot in resterende_lots
    )

    realiseret = afgang_beloeb - kostbasis_solgt
    urealiseret = ultimo_vaerdi - kostbasis_resterende

    alle_resterende_lots = [Tilgangslot("primo", resterende_primo_antal, primo_kurs)] + resterende_lots

    resultat = PapirBeregning(
        papir_id=papir_id,
        papirnavn=papirnavn,
        isin=isin,
        primo_antal=primo_antal,
        primo_kurs=primo_kurs,
        primo_vaerdi=primo_vaerdi,
        tilgang_antal=tilgang_antal,
        tilgang_beloeb=tilgang_beloeb,
        afgang_antal=afgang_antal,
        afgang_beloeb=afgang_beloeb,
        ultimo_antal=ultimo_antal,
        ultimo_kurs=ultimo_kurs,
        ultimo_vaerdi=ultimo_vaerdi,
        kostbasis_solgt=kostbasis_solgt,
        kostbasis_resterende=kostbasis_resterende,
        realiseret=realiseret,
        urealiseret=urealiseret,
        resterende_lots=alle_resterende_lots,
    )
    resultat.kontrolsum_diff = _kontroller(resultat)
    return resultat


def _kontroller(r: PapirBeregning) -> float:
    """Kontrolsum: Realiseret + Urealiseret skal være lig med den samlede
    ændring i formue: Ultimoværdi + Salgssum - Primoværdi - Købesum.
    Bruges som en indbygget selvtest af FIFO-fordelingen. Returnerer
    differencen (bør være ~0)."""
    kontrolsum = r.ultimo_vaerdi + r.afgang_beloeb - r.primo_vaerdi - r.tilgang_beloeb
    diff = kontrolsum - r.total
    if abs(diff) > 0.01:
        raise AssertionError(
            f"Kontrolsum stemmer ikke for '{r.papirnavn}': forventede {kontrolsum:.2f}, "
            f"fik realiseret+urealiseret = {r.total:.2f} (difference {diff:.2f})."
        )
    return diff


def beregn_alle(data: pd.DataFrame) -> list[PapirBeregning]:
    """Kører beregningen for alle værdipapirer i det standardiserede datasæt."""
    resultater = []
    for _, gruppe in data.groupby("papir_id", sort=False):
        resultater.append(beregn_for_papir(gruppe))
    return resultater


def resultater_til_dataframe(resultater: list[PapirBeregning]) -> pd.DataFrame:
    """Mellemresultat-tabel til visning i UI'en, så tallene kan afstemmes
    mod brugerens egen Excel-skabelon."""
    rows = []
    for r in resultater:
        rows.append(
            {
                "Papir": r.papirnavn,
                "ISIN": r.isin,
                "Primo antal": r.primo_antal,
                "Primo kurs": r.primo_kurs,
                "Primo værdi": r.primo_vaerdi,
                "Tilgang antal": r.tilgang_antal,
                "Tilgang beløb": r.tilgang_beloeb,
                "Afgang antal": r.afgang_antal,
                "Afgang beløb": r.afgang_beloeb,
                "Ultimo antal": r.ultimo_antal,
                "Ultimo kurs": r.ultimo_kurs,
                "Ultimo værdi": r.ultimo_vaerdi,
                "Realiseret gevinst/tab": round(r.realiseret, 2),
                "Urealiseret gevinst/tab": round(r.urealiseret, 2),
                "I alt": round(r.total, 2),
            }
        )
    return pd.DataFrame(rows)
