/**
 * Generering af CSV-fil klar til import i e-conomics kassekladde.
 *
 * Kolonneformatet (Type;Bilagsnr.;Dato;Konto;Beløb;Tekst;Afdeling;Dimension)
 * og fortegnskonventionen (positivt beløb = debet, negativt = kredit) er
 * valideret mod et virkeligt e-conomic bogføringseksempel og porteret fra
 * den afprøvede Python-version (kursregulering/csv_eksport.py). Afdeling
 * og Dimension er valgfrie e-conomic-felter — lad dem stå tomme hvis I
 * ikke bruger dem.
 *
 * Fortegnskonvention:
 * - Balancekontoen (aktiv) får gevinst/tab- eller kildeskat-beløbet direkte
 *   (positivt = debet = værdistigning/tilgodehavende).
 * - Resultatkontoen får det modsatte fortegn, så hvert bilag balancerer.
 * Tjek at det passer til jeres egen kontoplan.
 */

import type { PapirBeregning } from "@/lib/calculations/kursregulering";
import type { UdbytteResultat } from "@/lib/calculations/udbytte";

const TOLERANCE = 0.005; // under en halv øre anses for at være "ingen regulering"

export interface KassekladdeLinje {
  type: string;
  bilagsnr: number;
  dato: string; // ISO-dato (YYYY-MM-DD)
  konto: string;
  beloeb: number;
  tekst: string;
  afdeling?: string;
  dimension?: string;
}

function formatBeloebDansk(beloeb: number): string {
  const afrundet = Math.round(beloeb * 100) / 100;
  const [heltal, decimal] = Math.abs(afrundet).toFixed(2).split(".");
  const heltalMedTusindtal = heltal.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  const fortegn = afrundet < 0 ? "-" : "";
  return `${fortegn}${heltalMedTusindtal},${decimal}`;
}

function formatDatoDansk(iso: string): string {
  const [aar, maaned, dag] = iso.split("-");
  return `${dag}-${maaned}-${aar}`;
}

export interface KursreguleringEksportOptioner {
  resultatkonto: string;
  balancekonto: string;
  bogfoeringsdato: string; // ISO
  bilagstype?: string;
  startBilagsnummer?: number;
  afdeling?: string;
  dimension?: string;
}

export function byggKursreguleringLinjer(
  resultater: PapirBeregning[],
  optioner: KursreguleringEksportOptioner
): KassekladdeLinje[] {
  const { resultatkonto, balancekonto, bogfoeringsdato, afdeling, dimension } = optioner;
  const bilagstype = optioner.bilagstype ?? "Finansbilag";
  let bilagsnr = optioner.startBilagsnummer ?? 1;
  const linjer: KassekladdeLinje[] = [];

  for (const r of resultater) {
    for (const [label, beloeb] of [
      ["realiseret", r.realiseret],
      ["urealiseret", r.urealiseret],
    ] as const) {
      if (Math.abs(beloeb) < TOLERANCE) continue;
      const tekst = `Kursregulering ${r.papirnavn} – ${label} gevinst/tab`;

      linjer.push({ type: bilagstype, bilagsnr, dato: bogfoeringsdato, konto: balancekonto, beloeb, tekst, afdeling, dimension });
      linjer.push({ type: bilagstype, bilagsnr, dato: bogfoeringsdato, konto: resultatkonto, beloeb: -beloeb, tekst, afdeling, dimension });
      bilagsnr += 1;
    }
  }

  return linjer;
}

export interface UdbytteEksportOptioner {
  resultatkonto: string;
  bankkonto: string;
  danskSkattekonto: string;
  udenlandskSkattekonto: string;
  bilagstype?: string;
  startBilagsnummer?: number;
  afdeling?: string;
  dimension?: string;
}

export function byggUdbytteLinjer(
  resultater: UdbytteResultat[],
  optioner: UdbytteEksportOptioner
): KassekladdeLinje[] {
  const { resultatkonto, bankkonto, danskSkattekonto, udenlandskSkattekonto, afdeling, dimension } = optioner;
  const bilagstype = optioner.bilagstype ?? "Finansbilag";
  let bilagsnr = optioner.startBilagsnummer ?? 1;
  const linjer: KassekladdeLinje[] = [];

  for (const r of resultater) {
    const dato = r.dato ?? new Date().toISOString().slice(0, 10);
    const tekst = `Udbytte ${r.papirnavn} (${r.landnavn})`;

    linjer.push({ type: bilagstype, bilagsnr, dato, konto: resultatkonto, beloeb: -r.bruttoUdbytte, tekst, afdeling, dimension });
    if (Math.abs(r.kildeskat) >= TOLERANCE) {
      const skattekonto = r.erDansk ? danskSkattekonto : udenlandskSkattekonto;
      linjer.push({ type: bilagstype, bilagsnr, dato, konto: skattekonto, beloeb: r.kildeskat, tekst, afdeling, dimension });
    }
    linjer.push({ type: bilagstype, bilagsnr, dato, konto: bankkonto, beloeb: r.nettoUdbytte, tekst, afdeling, dimension });

    bilagsnr += 1;
  }

  return linjer;
}

export function genererCsv(linjer: KassekladdeLinje[]): string {
  const brugerAfdeling = linjer.some((l) => l.afdeling);
  const brugerDimension = linjer.some((l) => l.dimension);

  const header = ["Type", "Bilagsnr.", "Dato", "Konto", "Beløb", "Tekst"];
  if (brugerAfdeling) header.push("Afdeling");
  if (brugerDimension) header.push("Dimension");

  const raekker = linjer.map((l) => {
    const felter = [
      l.type,
      String(l.bilagsnr),
      formatDatoDansk(l.dato),
      l.konto,
      formatBeloebDansk(l.beloeb),
      l.tekst,
    ];
    if (brugerAfdeling) felter.push(l.afdeling ?? "");
    if (brugerDimension) felter.push(l.dimension ?? "");
    return felter;
  });

  const csvLinjer = [header, ...raekker].map((felter) =>
    felter.map(escapeCsvFelt).join(";")
  );

  // ﻿ (BOM) sikrer at Excel/e-conomic læser danske bogstaver (æøå) korrekt
  return "﻿" + csvLinjer.join("\r\n") + "\r\n";
}

function escapeCsvFelt(felt: string): string {
  if (felt.includes(";") || felt.includes('"') || felt.includes("\n")) {
    return `"${felt.replace(/"/g, '""')}"`;
  }
  return felt;
}
