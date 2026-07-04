import { beregnAlle, type Transaktion } from "../src/lib/calculations/kursregulering";
import { beregnAlleUdbytter, type UdbytteLinje } from "../src/lib/calculations/udbytte";
import { byggKursreguleringLinjer, byggUdbytteLinjer, genererCsv } from "../src/lib/csv/economic";

let raekke = 1;
function t(papirId: string, papirnavn: string, type: Transaktion["type"], dato: string | null, antal: number | null, kurs: number | null): Transaktion {
  const beloeb = antal !== null && kurs !== null ? antal * kurs : null;
  return { raekke: raekke++, papirId, papirnavn, isin: papirId, type, dato, antal, kurs, beloeb };
}

const data: Transaktion[] = [
  t("NOVO", "Novo Nordisk B", "primo", "2024-01-01", 100, 700),
  t("NOVO", "Novo Nordisk B", "tilgang", "2024-03-15", 50, 800),
  t("NOVO", "Novo Nordisk B", "afgang", "2024-09-10", 30, 900),
  t("NOVO", "Novo Nordisk B", "ultimo", "2024-12-31", 120, 850),
];

const resultater = beregnAlle(data);
const linjer = byggKursreguleringLinjer(resultater, {
  resultatkonto: "7220",
  balancekonto: "6820",
  bogfoeringsdato: "2024-12-31",
});

console.log(genererCsv(linjer));

const udbytteLinjer: UdbytteLinje[] = [
  { papirnavn: "Novo Nordisk", land: "Danmark", beloebstype: "netto", beloeb: 18823.41, dato: "2024-03-26" },
];
const udbytteResultater = beregnAlleUdbytter(udbytteLinjer);
const udbytteKladde = byggUdbytteLinjer(udbytteResultater, {
  resultatkonto: "2100",
  bankkonto: "5820",
  danskSkattekonto: "6210",
  udenlandskSkattekonto: "6220",
});
console.log(genererCsv(udbytteKladde));
