import { beregnAlle, validerTransaktioner, harFejl, type Transaktion } from "../src/lib/calculations/kursregulering";

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

  t("VOLVO", "Volvo B", "primo", "2024-01-01", 200, 220),
  t("VOLVO", "Volvo B", "tilgang", "2024-05-10", 100, 230),
  t("VOLVO", "Volvo B", "afgang", "2024-04-01", 50, 240),
  t("VOLVO", "Volvo B", "ultimo", "2024-12-31", 250, 235),

  t("OERSTED", "Ørsted", "tilgang", "2024-02-15", 80, 550),
  t("OERSTED", "Ørsted", "ultimo", "2024-12-31", 80, 600),
];

const fund = validerTransaktioner(data);
console.log("fund:", fund);
console.log("harFejl:", harFejl(fund));

const resultater = beregnAlle(data);
console.table(
  resultater.map((r) => ({
    papir: r.papirnavn,
    realiseret: r.realiseret,
    urealiseret: r.urealiseret,
    kontrolsumDiff: r.kontrolsumDiff,
  }))
);

const forventet: Record<string, { realiseret: number; urealiseret: number }> = {
  "Novo Nordisk B": { realiseret: 6000, urealiseret: 13000 },
  "Volvo B": { realiseret: 1000, urealiseret: 2750 },
  Ørsted: { realiseret: 0, urealiseret: 4000 },
};

for (const r of resultater) {
  const f = forventet[r.papirnavn];
  const ok = Math.abs(r.realiseret - f.realiseret) < 0.01 && Math.abs(r.urealiseret - f.urealiseret) < 0.01;
  console.log(`${ok ? "OK " : "FEJL"} ${r.papirnavn}: realiseret=${r.realiseret} urealiseret=${r.urealiseret}`);
  if (!ok) process.exitCode = 1;
}
