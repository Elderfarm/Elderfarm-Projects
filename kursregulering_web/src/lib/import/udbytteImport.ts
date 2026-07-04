import { LANDE_NAVNE, parseBeloeb, type Beloebstype } from "@/lib/calculations/udbytte";
import { genkendKolonner, parseCsvTekst, parseExcelFil, type RaaTabel, type RaaVaerdi } from "@/lib/import/fileParsing";

export interface ImporteretUdbytteRaekke {
  papirnavn: string;
  land: string;
  beloebstype: Beloebstype;
  beloeb: string;
  dato: string;
}

const SYNONYMER: Record<string, string[]> = {
  papirnavn: ["papirnavn", "navn", "værdipapir", "papir", "titel"],
  dato: ["dato", "betalingsdato", "handelsdato"],
  land: ["land", "lande"],
  landekode: ["landekode", "land-kode", "kode"],
  isin: ["isin"],
  type: ["type", "beløbstype", "netto/brutto", "brutto/netto"],
  beloebNetto: ["netto udbytte", "nettoudbytte", "netto"],
  beloebBrutto: ["brutto udbytte", "bruttoudbytte", "brutto"],
  beloebGenerisk: ["beløb", "modtaget beløb", "udbytte"],
};

function tilTekst(v: RaaVaerdi): string {
  return v === null || v === undefined ? "" : String(v).trim();
}

function udledLandTekst(landekode: RaaVaerdi, isin: RaaVaerdi): string {
  const kodeTekst = tilTekst(landekode).toUpperCase();
  if (kodeTekst) return LANDE_NAVNE[kodeTekst] ?? kodeTekst;
  const isinTekst = tilTekst(isin);
  if (isinTekst.length >= 2) return isinTekst.slice(0, 2).toUpperCase();
  return "";
}

function tilIsoDato(v: RaaVaerdi): string {
  const tekst = tilTekst(v);
  if (!tekst) return "";
  // Allerede ISO (fra ExcelJS' dato-celler eller en ISO-tekststreng)
  if (/^\d{4}-\d{2}-\d{2}/.test(tekst)) return tekst.slice(0, 10);
  // Dansk format DD-MM-ÅÅÅÅ eller DD/MM/ÅÅÅÅ
  const match = tekst.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
  if (match) {
    const [, dag, maaned, aar] = match;
    return `${aar}-${maaned.padStart(2, "0")}-${dag.padStart(2, "0")}`;
  }
  return "";
}

function raekkerTilUdbytte(header: RaaVaerdi[], data: RaaTabel): ImporteretUdbytteRaekke[] {
  const mapping = genkendKolonner(header, SYNONYMER);
  const hent = (raekke: RaaVaerdi[], felt: string): RaaVaerdi =>
    felt in mapping ? raekke[mapping[felt]] ?? null : null;

  return data.map((raekke) => {
    let beloebstype: Beloebstype = "netto";
    let beloebRaa: RaaVaerdi = null;

    if ("beloebNetto" in mapping) {
      beloebstype = "netto";
      beloebRaa = hent(raekke, "beloebNetto");
    } else if ("beloebBrutto" in mapping) {
      beloebstype = "brutto";
      beloebRaa = hent(raekke, "beloebBrutto");
    } else if ("beloebGenerisk" in mapping) {
      beloebRaa = hent(raekke, "beloebGenerisk");
    }

    const typeRaa = tilTekst(hent(raekke, "type")).toLowerCase();
    if (typeRaa.startsWith("net")) beloebstype = "netto";
    else if (typeRaa.startsWith("brut")) beloebstype = "brutto";

    const beloeb = parseBeloeb(beloebRaa as string | number | null);

    return {
      papirnavn: tilTekst(hent(raekke, "papirnavn")),
      land: udledLandTekst(hent(raekke, "landekode") ?? hent(raekke, "land"), hent(raekke, "isin")),
      beloebstype,
      beloeb: beloeb === null ? "" : String(beloeb),
      dato: tilIsoDato(hent(raekke, "dato")),
    };
  });
}

export async function importerUdbytteFil(fil: File): Promise<ImporteretUdbytteRaekke[]> {
  const erCsv = fil.name.toLowerCase().endsWith(".csv");
  const tabel = erCsv ? parseCsvTekst(await fil.text()) : await parseExcelFil(fil);
  if (tabel.length < 2) return [];
  const [header, ...data] = tabel;
  return raekkerTilUdbytte(header, data);
}
