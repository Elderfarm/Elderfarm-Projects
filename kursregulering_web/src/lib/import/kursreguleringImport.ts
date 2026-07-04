import { genkendKolonner, parseCsvTekst, parseExcelFil, type RaaTabel, type RaaVaerdi } from "@/lib/import/fileParsing";
import type { TransaktionType } from "@/lib/calculations/kursregulering";

export interface ImporteretKursreguleringRaekke {
  papirnavn: string;
  isin: string;
  type: TransaktionType | "";
  dato: string;
  antal: string;
  kurs: string;
}

const SYNONYMER: Record<string, string[]> = {
  isin: ["isin"],
  papirnavn: ["papirnavn", "navn", "værdipapir", "papir", "titel"],
  type: ["type", "transaktionstype", "posteringstype"],
  dato: ["dato", "transaktionsdato", "handelsdato"],
  antal: ["antal", "stk", "stykker"],
  kurs: ["kurs", "pris", "kurs pr stk", "pris pr stk"],
};

const GYLDIGE_TYPER: TransaktionType[] = ["primo", "tilgang", "afgang", "ultimo"];

function tilTekst(v: RaaVaerdi): string {
  return v === null || v === undefined ? "" : String(v).trim();
}

function tilTal(v: RaaVaerdi): string {
  const tekst = tilTekst(v);
  if (!tekst) return "";
  const tal = Number(tekst.replace(",", "."));
  return Number.isFinite(tal) ? String(tal) : "";
}

function tilIsoDato(v: RaaVaerdi): string {
  const tekst = tilTekst(v);
  if (!tekst) return "";
  if (/^\d{4}-\d{2}-\d{2}/.test(tekst)) return tekst.slice(0, 10);
  const match = tekst.match(/^(\d{1,2})[-/](\d{1,2})[-/](\d{4})$/);
  if (match) {
    const [, dag, maaned, aar] = match;
    return `${aar}-${maaned.padStart(2, "0")}-${dag.padStart(2, "0")}`;
  }
  return "";
}

function raekkerTilKursregulering(header: RaaVaerdi[], data: RaaTabel): ImporteretKursreguleringRaekke[] {
  const mapping = genkendKolonner(header, SYNONYMER);
  const hent = (raekke: RaaVaerdi[], felt: string): RaaVaerdi =>
    felt in mapping ? raekke[mapping[felt]] ?? null : null;

  return data.map((raekke) => {
    const typeRaa = tilTekst(hent(raekke, "type")).toLowerCase();
    const type = (GYLDIGE_TYPER.find((t) => t === typeRaa) ?? "") as TransaktionType | "";

    return {
      papirnavn: tilTekst(hent(raekke, "papirnavn")) || tilTekst(hent(raekke, "isin")),
      isin: tilTekst(hent(raekke, "isin")),
      type,
      dato: tilIsoDato(hent(raekke, "dato")),
      antal: tilTal(hent(raekke, "antal")),
      kurs: tilTal(hent(raekke, "kurs")),
    };
  });
}

export async function importerKursreguleringFil(fil: File): Promise<ImporteretKursreguleringRaekke[]> {
  const erCsv = fil.name.toLowerCase().endsWith(".csv");
  const tabel = erCsv ? parseCsvTekst(await fil.text()) : await parseExcelFil(fil);
  if (tabel.length < 2) return [];
  const [header, ...data] = tabel;
  return raekkerTilKursregulering(header, data);
}
