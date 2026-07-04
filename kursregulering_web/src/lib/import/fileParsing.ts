/**
 * Generisk fil-parsing til fil-upload (Excel/CSV), brugt som en genvej til
 * at udfylde de redigerbare tabeller i UI'en. Kolonnenavne genkendes
 * fleksibelt (samme princip som parser.py/udbytte.py i Python-versionen).
 */
import ExcelJS from "exceljs";

export type RaaVaerdi = string | number | null;
export type RaaTabel = RaaVaerdi[][];

/** Parser CSV-tekst til rækker af celleværdier. Understøtter citerede felter
 * og genkender selv om filen bruger komma eller semikolon som separator. */
export function parseCsvTekst(tekst: string): RaaTabel {
  const renset = tekst.replace(/^﻿/, "").replace(/\r\n/g, "\n");
  const foersteLinje = renset.split("\n")[0] ?? "";
  const separator = (foersteLinje.match(/;/g)?.length ?? 0) >= (foersteLinje.match(/,/g)?.length ?? 0) ? ";" : ",";

  const raekker: RaaTabel = [];
  let felt = "";
  let raekke: RaaVaerdi[] = [];
  let iCitat = false;

  for (let i = 0; i < renset.length; i++) {
    const c = renset[i];
    if (iCitat) {
      if (c === '"') {
        if (renset[i + 1] === '"') {
          felt += '"';
          i++;
        } else {
          iCitat = false;
        }
      } else {
        felt += c;
      }
    } else if (c === '"') {
      iCitat = true;
    } else if (c === separator) {
      raekke.push(felt);
      felt = "";
    } else if (c === "\n") {
      raekke.push(felt);
      raekker.push(raekke);
      raekke = [];
      felt = "";
    } else {
      felt += c;
    }
  }
  if (felt.length || raekke.length) {
    raekke.push(felt);
    raekker.push(raekke);
  }

  return raekker.filter((r) => r.some((v) => String(v ?? "").trim() !== ""));
}

/** Parser en Excel-fil (første ark) til rækker af celleværdier. */
export async function parseExcelFil(fil: File): Promise<RaaTabel> {
  const buffer = await fil.arrayBuffer();
  const workbook = new ExcelJS.Workbook();
  await workbook.xlsx.load(buffer);
  const ark = workbook.worksheets[0];
  if (!ark) return [];

  const raekker: RaaTabel = [];
  ark.eachRow((row) => {
    const vaerdier: RaaVaerdi[] = [];
    // ExcelJS' row.values er 1-indekseret med et tomt element 0 — spring det over.
    const raa = row.values as ExcelJS.CellValue[];
    for (let i = 1; i < raa.length; i++) {
      const v = raa[i];
      if (v === null || v === undefined) {
        vaerdier.push(null);
      } else if (v instanceof Date) {
        vaerdier.push(v.toISOString().slice(0, 10));
      } else if (typeof v === "object" && "text" in v) {
        vaerdier.push(String((v as { text: unknown }).text));
      } else if (typeof v === "object" && "result" in v) {
        vaerdier.push((v as { result: RaaVaerdi }).result);
      } else {
        vaerdier.push(v as RaaVaerdi);
      }
    }
    if (vaerdier.some((v) => String(v ?? "").trim() !== "")) {
      raekker.push(vaerdier);
    }
  });

  return raekker;
}

/** Normaliserer et kolonnenavn så det er robust at sammenligne. */
function normaliserHeader(navn: RaaVaerdi): string {
  return String(navn ?? "")
    .trim()
    .toLowerCase()
    .replace(/\./g, "");
}

/** Finder hvilken kolonneindex der svarer til hvert standardfelt, ud fra en
 * liste af accepterede synonymer pr. felt. */
export function genkendKolonner(
  headerRaekke: RaaVaerdi[],
  synonymer: Record<string, string[]>
): Record<string, number> {
  const normaliserede = headerRaekke.map(normaliserHeader);
  const mapping: Record<string, number> = {};

  for (const [felt, muligheder] of Object.entries(synonymer)) {
    for (const mulighed of muligheder) {
      const index = normaliserede.indexOf(mulighed);
      if (index !== -1) {
        mapping[felt] = index;
        break;
      }
    }
  }

  return mapping;
}
