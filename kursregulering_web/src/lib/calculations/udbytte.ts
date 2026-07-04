/**
 * Beregning af udbytte: bruttoudbytte og kildeskat pr. udbyttebetaling.
 *
 * Port af den validerede Python-model i kursregulering/udbytte.py — samme
 * facit-tal, samme bevidst forenklede model (ingen opdeling af udenlandsk
 * kildeskat i "tilbagesøges via selvangivelse" vs. "via banken" efter
 * dobbeltbeskatningsoverenskomstens maks-sats).
 *
 * - For hver betaling kender man ÉT beløb — enten NETTO (det der reelt
 *   blev indsat på bankkontoen) eller BRUTTO (det fulde udbytte før skat).
 * - Det andet beløb findes ved at bruge den kendte nettoprocent for
 *   kildelandet: Brutto = Netto / nettoprocent, eller Netto = Brutto × nettoprocent.
 * - Kildeskat = Bruttoudbytte − Nettoudbytte.
 * - Beløbene opdeles i "Dansk" og "Udenlandsk" afhængigt af kildelandet, da
 *   de bogføres på hver sin tilgodehavende-konto.
 */

export const LANDE_NETTOPROCENT: Record<string, number> = {
  US: 85,
  CH: 65,
  FR: 75,
  ES: 81,
  DE: 73.625,
  GB: 100,
  JP: 100 - 15.32,
  BE: 85,
  IT: 74,
  IE: 75,
  PO: 85,
  CA: 85,
  SE: 85,
  FI: 65,
  NO: 75,
  SG: 100,
  TH: 90,
  KI: 90,
  NL: 85,
  TW: 90,
  DK: 78,
  LU: 85,
  IL: 75,
  AUD: 70,
};

export const LANDE_NAVNE: Record<string, string> = {
  US: "USA",
  CH: "Schweiz",
  FR: "Frankrig",
  ES: "Spanien",
  DE: "Tyskland",
  GB: "Storbritannien",
  JP: "Japan",
  BE: "Belgien",
  IT: "Italien",
  IE: "Irland",
  PO: "Polen",
  CA: "Canada",
  SE: "Sverige",
  FI: "Finland",
  NO: "Norge",
  SG: "Singapore",
  TH: "Thailand",
  KI: "Kina",
  NL: "Holland",
  TW: "Taiwan",
  DK: "Danmark",
  LU: "Luxembourg",
  IL: "Israel",
  AUD: "Australien",
};

export const NAVN_TIL_LANDEKODE: Record<string, string> = Object.fromEntries(
  Object.entries(LANDE_NAVNE).map(([kode, navn]) => [navn.toUpperCase(), kode])
);

export type Beloebstype = "netto" | "brutto";

export interface UdbytteLinje {
  papirnavn: string;
  /** Landenavn, landekode eller ISIN — se udledLandekode() */
  land: string;
  beloebstype: Beloebstype;
  beloeb: number | null;
  dato: string | null; // ISO-dato (YYYY-MM-DD) eller null
}

export interface UdbytteResultat {
  papirnavn: string;
  dato: string | null;
  landekode: string;
  landnavn: string;
  erDansk: boolean;
  nettoUdbytte: number;
  bruttoUdbytte: number;
  kildeskat: number;
}

export type FundNiveau = "fejl" | "advarsel";

export interface UdbytteFund {
  raekke: number;
  papirnavn: string;
  niveau: FundNiveau;
  besked: string;
}

/** Udleder landekode fra en Land-værdi: accepterer både "DK" og "Danmark". */
export function udledLandekode(land: string | null | undefined): string {
  if (!land) return "";
  const tekst = land.trim().toUpperCase();
  return NAVN_TIL_LANDEKODE[tekst] ?? tekst;
}

/** Fortolker et beløb robust: tal, "18823.41", "18.823,41" eller "18823,41". */
export function parseBeloeb(vaerdi: string | number | null | undefined): number | null {
  if (vaerdi === null || vaerdi === undefined) return null;
  if (typeof vaerdi === "number") return Number.isFinite(vaerdi) ? vaerdi : null;

  let tekst = vaerdi.trim().replace(/\s/g, "").replace(/kr\.?/i, "");
  if (!tekst) return null;

  if (tekst.includes(",") && tekst.includes(".")) {
    tekst = tekst.replace(/\./g, "").replace(",", ".");
  } else if (tekst.includes(",")) {
    tekst = tekst.replace(",", ".");
  }

  const tal = Number(tekst);
  return Number.isFinite(tal) ? tal : null;
}

export function validerUdbytte(linjer: UdbytteLinje[]): UdbytteFund[] {
  const fund: UdbytteFund[] = [];

  linjer.forEach((linje, index) => {
    const raekke = index + 1;
    const papirnavn = linje.papirnavn.trim();

    if (!papirnavn) {
      fund.push({ raekke, papirnavn, niveau: "fejl", besked: "Mangler papirnavn." });
    }
    if (linje.beloeb === null) {
      fund.push({ raekke, papirnavn, niveau: "fejl", besked: "Mangler beløb." });
    } else if (linje.beloeb <= 0) {
      fund.push({ raekke, papirnavn, niveau: "fejl", besked: "Beløbet skal være positivt." });
    }

    const landekode = udledLandekode(linje.land);
    if (!landekode) {
      fund.push({
        raekke,
        papirnavn,
        niveau: "fejl",
        besked: "Mangler land/landekode — kan ikke finde skattesats.",
      });
    } else if (!(landekode in LANDE_NETTOPROCENT)) {
      fund.push({
        raekke,
        papirnavn,
        niveau: "fejl",
        besked: `Kender ikke skattesatsen for landekoden '${landekode}'. Ret landekoden, eller tilføj landet i LANDE_NETTOPROCENT.`,
      });
    }

    if (!linje.dato) {
      fund.push({ raekke, papirnavn, niveau: "advarsel", besked: "Mangler betalingsdato." });
    }
  });

  return fund;
}

export function harFejl(fund: UdbytteFund[]): boolean {
  return fund.some((f) => f.niveau === "fejl");
}

export function beregnUdbytteLinje(linje: UdbytteLinje): UdbytteResultat {
  const landekode = udledLandekode(linje.land);
  const nettoprocent = LANDE_NETTOPROCENT[landekode] / 100;
  const beloeb = linje.beloeb ?? 0;

  const nettoUdbytte = linje.beloebstype === "brutto" ? beloeb * nettoprocent : beloeb;
  const bruttoUdbytte = linje.beloebstype === "brutto" ? beloeb : beloeb / nettoprocent;
  const kildeskat = bruttoUdbytte - nettoUdbytte;

  return {
    papirnavn: linje.papirnavn,
    dato: linje.dato,
    landekode,
    landnavn: LANDE_NAVNE[landekode] ?? landekode,
    erDansk: landekode === "DK",
    nettoUdbytte,
    bruttoUdbytte,
    kildeskat,
  };
}

export function beregnAlleUdbytter(linjer: UdbytteLinje[]): UdbytteResultat[] {
  return linjer.map(beregnUdbytteLinje);
}

export interface UdbytteOpsummering {
  danskBrutto: number;
  danskKildeskat: number;
  udenlandskBrutto: number;
  udenlandskKildeskat: number;
  nettoIAlt: number;
}

export function opsummerUdbytter(resultater: UdbytteResultat[]): UdbytteOpsummering {
  const dansk = resultater.filter((r) => r.erDansk);
  const udenlandsk = resultater.filter((r) => !r.erDansk);
  const sum = (rows: UdbytteResultat[], vaelg: (r: UdbytteResultat) => number) =>
    rows.reduce((total, r) => total + vaelg(r), 0);

  return {
    danskBrutto: sum(dansk, (r) => r.bruttoUdbytte),
    danskKildeskat: sum(dansk, (r) => r.kildeskat),
    udenlandskBrutto: sum(udenlandsk, (r) => r.bruttoUdbytte),
    udenlandskKildeskat: sum(udenlandsk, (r) => r.kildeskat),
    nettoIAlt: sum(resultater, (r) => r.nettoUdbytte),
  };
}
