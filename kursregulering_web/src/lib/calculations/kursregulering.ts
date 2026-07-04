/**
 * Kursregulering af noterede aktier efter LAGERPRINCIPPET.
 *
 * Port af den validerede Python-model i kursregulering/beregning.py og
 * validering.py — samme facit-tal, samme kontrolsum-assertion.
 *
 * VIGTIGT — sådan virker lagerprincippet (modsat realisationsprincippet):
 * - `Primo kurs` er IKKE den oprindelige anskaffelsessum. Det er sidste
 *   års `Ultimo kurs`, som allerede er blevet beskattet én gang sidste år.
 * - Tilgange i året har basis = den faktiske købspris.
 * - Der beskattes hvert år, uanset om papiret sælges eller ej.
 * - FIFO afgør om et solgt stykke stammer fra primo-beholdningen eller en
 *   tilgang i året (primo anses altid for anskaffet før årets tilgange).
 */

export type TransaktionType = "primo" | "tilgang" | "afgang" | "ultimo";

export interface Transaktion {
  raekke: number;
  papirId: string;
  papirnavn: string;
  isin: string;
  type: TransaktionType;
  dato: string | null; // ISO-dato (YYYY-MM-DD)
  antal: number | null;
  kurs: number | null;
  beloeb: number | null;
}

const TOLERANCE = 1e-6;

// ---------------------------------------------------------------------------
// Validering
// ---------------------------------------------------------------------------

export type FundNiveau = "fejl" | "advarsel";

export interface ValideringsFund {
  papirId: string;
  papirnavn: string;
  niveau: FundNiveau;
  kategori: string;
  besked: string;
  raekker: number[];
}

function grupperPrPapir(data: Transaktion[]): Map<string, Transaktion[]> {
  const grupper = new Map<string, Transaktion[]>();
  for (const t of data) {
    const liste = grupper.get(t.papirId) ?? [];
    liste.push(t);
    grupper.set(t.papirId, liste);
  }
  return grupper;
}

function summer(linjer: Transaktion[], type: TransaktionType, felt: "antal" | "beloeb"): number {
  return linjer
    .filter((l) => l.type === type)
    .reduce((sum, l) => sum + (l[felt] ?? 0), 0);
}

function tjekSaldo(gruppe: Transaktion[]): ValideringsFund[] {
  const ultimo = gruppe.filter((l) => l.type === "ultimo");
  if (ultimo.length === 0) return [];

  const primoAntal = summer(gruppe, "primo", "antal");
  const tilgangAntal = summer(gruppe, "tilgang", "antal");
  const afgangAntal = summer(gruppe, "afgang", "antal");
  const ultimoAntal = summer(gruppe, "ultimo", "antal");
  const forventet = primoAntal + tilgangAntal - afgangAntal;

  if (Math.abs(forventet - ultimoAntal) > TOLERANCE) {
    return [
      {
        papirId: gruppe[0].papirId,
        papirnavn: gruppe[0].papirnavn,
        niveau: "fejl",
        kategori: "Saldo-kontrol",
        besked: `Primo (${primoAntal}) + Tilgange (${tilgangAntal}) - Afgange (${afgangAntal}) = ${forventet}, men Ultimo antal er ${ultimoAntal}. Differencen er ${ultimoAntal - forventet} stk.`,
        raekker: gruppe.map((l) => l.raekke),
      },
    ];
  }
  return [];
}

function tjekManglendeData(gruppe: Transaktion[]): ValideringsFund[] {
  const fund: ValideringsFund[] = [];
  for (const l of gruppe.filter((l) => l.type !== "primo" && l.type !== "ultimo")) {
    const mangler: string[] = [];
    if (!l.dato) mangler.push("Dato");
    if (l.antal === null) mangler.push("Antal");
    if (l.kurs === null) mangler.push("Kurs");
    if (mangler.length) {
      fund.push({
        papirId: l.papirId,
        papirnavn: l.papirnavn,
        niveau: "fejl",
        kategori: "Manglende data",
        besked: `${l.type[0].toUpperCase()}${l.type.slice(1)}-linje mangler: ${mangler.join(", ")}.`,
        raekker: [l.raekke],
      });
    }
  }
  return fund;
}

function tjekNegativeVaerdier(gruppe: Transaktion[]): ValideringsFund[] {
  const fund: ValideringsFund[] = [];
  for (const l of gruppe) {
    if (l.type === "tilgang" && l.antal !== null && l.antal < 0) {
      fund.push({
        papirId: l.papirId,
        papirnavn: l.papirnavn,
        niveau: "fejl",
        kategori: "Urealistisk værdi",
        besked: `Negativt antal (${l.antal}) ved Tilgang.`,
        raekker: [l.raekke],
      });
    }
    if (l.kurs !== null && l.kurs < 0) {
      fund.push({
        papirId: l.papirId,
        papirnavn: l.papirnavn,
        niveau: "fejl",
        kategori: "Urealistisk værdi",
        besked: `Negativ kurs (${l.kurs}) på ${l.type}-linje.`,
        raekker: [l.raekke],
      });
    }
    if (l.kurs === 0) {
      fund.push({
        papirId: l.papirId,
        papirnavn: l.papirnavn,
        niveau: "advarsel",
        kategori: "Urealistisk værdi",
        besked: `Kurs = 0 på ${l.type}-linje. Kontrollér om det er korrekt.`,
        raekker: [l.raekke],
      });
    }
  }
  return fund;
}

function tjekDatoRaekkefoelge(gruppe: Transaktion[]): ValideringsFund[] {
  const tilgange = gruppe.filter((l) => l.type === "tilgang" && l.dato);
  const afgange = gruppe.filter((l) => l.type === "afgang" && l.dato);
  if (!tilgange.length || !afgange.length) return [];

  const tidligsteTilgang = tilgange.reduce((min, l) => (l.dato! < min ? l.dato! : min), tilgange[0].dato!);

  return afgange
    .filter((l) => l.dato! < tidligsteTilgang)
    .map((l) => ({
      papirId: l.papirId,
      papirnavn: l.papirnavn,
      niveau: "advarsel" as const,
      kategori: "Dato-rækkefølge",
      besked: `Afgang den ${l.dato} ligger før den tidligste Tilgang (${tidligsteTilgang}). Tjek at FIFO-rækkefølgen er korrekt.`,
      raekker: [l.raekke],
    }));
}

function tjekDubletter(gruppe: Transaktion[]): ValideringsFund[] {
  const set = new Map<string, Transaktion[]>();
  for (const l of gruppe) {
    const noegle = `${l.type}|${l.dato}|${l.antal}|${l.kurs}`;
    const liste = set.get(noegle) ?? [];
    liste.push(l);
    set.set(noegle, liste);
  }
  const fund: ValideringsFund[] = [];
  for (const linjer of set.values()) {
    if (linjer.length < 2) continue;
    for (const l of linjer) {
      fund.push({
        papirId: l.papirId,
        papirnavn: l.papirnavn,
        niveau: "advarsel",
        kategori: "Mulig dublet",
        besked: `Identisk linje findes flere gange (${l.type}, ${l.dato ?? "?"}, antal ${l.antal}, kurs ${l.kurs}). Kontrollér for dobbelt-indtastning.`,
        raekker: [l.raekke],
      });
    }
  }
  return fund;
}

function tjekPrimoUltimoTilstedevaerelse(gruppe: Transaktion[]): ValideringsFund[] {
  if (gruppe.some((l) => l.type === "ultimo")) return [];
  return [
    {
      papirId: gruppe[0].papirId,
      papirnavn: gruppe[0].papirnavn,
      niveau: "fejl",
      kategori: "Manglende Ultimo",
      besked: "Ingen Ultimo-linje fundet. Kan ikke beregne urealiseret gevinst/tab.",
      raekker: gruppe.map((l) => l.raekke),
    },
  ];
}

function tjekBeloebKonsistens(gruppe: Transaktion[]): ValideringsFund[] {
  const fund: ValideringsFund[] = [];
  for (const l of gruppe) {
    if (l.antal === null || l.kurs === null || l.beloeb === null) continue;
    const forventet = l.antal * l.kurs;
    if (Math.abs(forventet) > 0 && Math.abs(l.beloeb - forventet) / Math.max(Math.abs(forventet), 1) > 0.01) {
      fund.push({
        papirId: l.papirId,
        papirnavn: l.papirnavn,
        niveau: "advarsel",
        kategori: "Beløb stemmer ikke",
        besked: `Beløb (${l.beloeb}) afviger fra Antal × Kurs (${forventet}) på ${l.type}-linje. Kan skyldes kurtage/gebyrer.`,
        raekker: [l.raekke],
      });
    }
  }
  return fund;
}

const ALLE_TJEK = [
  tjekSaldo,
  tjekManglendeData,
  tjekNegativeVaerdier,
  tjekDatoRaekkefoelge,
  tjekDubletter,
  tjekPrimoUltimoTilstedevaerelse,
  tjekBeloebKonsistens,
];

export function validerTransaktioner(data: Transaktion[]): ValideringsFund[] {
  const fund: ValideringsFund[] = [];
  for (const gruppe of grupperPrPapir(data).values()) {
    for (const tjek of ALLE_TJEK) {
      fund.push(...tjek(gruppe));
    }
  }
  return fund;
}

export function harFejl(fund: ValideringsFund[]): boolean {
  return fund.some((f) => f.niveau === "fejl");
}

export interface PapirOversigt {
  papirId: string;
  papirnavn: string;
  isin: string;
  status: "OK" | "Advarsel" | "Fejl";
  antalFejl: number;
  antalAdvarsler: number;
}

export function opsummerPrPapir(data: Transaktion[], fund: ValideringsFund[]): PapirOversigt[] {
  const oversigt: PapirOversigt[] = [];
  for (const gruppe of grupperPrPapir(data).values()) {
    const papirId = gruppe[0].papirId;
    const papirFund = fund.filter((f) => f.papirId === papirId);
    const antalFejl = papirFund.filter((f) => f.niveau === "fejl").length;
    const antalAdvarsler = papirFund.filter((f) => f.niveau === "advarsel").length;
    oversigt.push({
      papirId,
      papirnavn: gruppe[0].papirnavn,
      isin: gruppe[0].isin,
      status: antalFejl ? "Fejl" : antalAdvarsler ? "Advarsel" : "OK",
      antalFejl,
      antalAdvarsler,
    });
  }
  return oversigt;
}

// ---------------------------------------------------------------------------
// Beregning
// ---------------------------------------------------------------------------

interface Tilgangslot {
  antal: number;
  kurs: number;
}

export interface PapirBeregning {
  papirId: string;
  papirnavn: string;
  isin: string;
  primoAntal: number;
  primoKurs: number;
  primoVaerdi: number;
  tilgangAntal: number;
  tilgangBeloeb: number;
  afgangAntal: number;
  afgangBeloeb: number;
  ultimoAntal: number;
  ultimoKurs: number;
  ultimoVaerdi: number;
  realiseret: number;
  urealiseret: number;
  kontrolsumDiff: number;
}

function vaegtetLinje(gruppe: Transaktion[], type: TransaktionType): [number, number, number] {
  const linjer = gruppe.filter((l) => l.type === type);
  if (!linjer.length) return [0, 0, 0];
  const antal = linjer.reduce((s, l) => s + (l.antal ?? 0), 0);
  const beloeb = linjer.reduce((s, l) => s + (l.beloeb ?? 0), 0);
  const kurs = antal ? beloeb / antal : 0;
  return [antal, beloeb, kurs];
}

function byggTilgangslots(gruppe: Transaktion[]): Tilgangslot[] {
  return gruppe
    .filter((l) => l.type === "tilgang")
    .slice()
    .sort((a, b) => {
      if (!a.dato) return 1;
      if (!b.dato) return -1;
      return a.dato < b.dato ? -1 : a.dato > b.dato ? 1 : 0;
    })
    .map((l) => ({ antal: l.antal ?? 0, kurs: l.kurs ?? 0 }));
}

function fordelFifo(
  primoAntal: number,
  primoKurs: number,
  tilgangslots: Tilgangslot[],
  afgangAntalTotal: number
): { kostbasisSolgt: number; resterendePrimoAntal: number; resterendeLots: Tilgangslot[] } {
  let atSaelge = afgangAntalTotal;

  const solgtFraPrimo = Math.min(atSaelge, primoAntal);
  const resterendePrimoAntal = primoAntal - solgtFraPrimo;
  let kostbasisSolgt = solgtFraPrimo * primoKurs;
  atSaelge -= solgtFraPrimo;

  const resterendeLots: Tilgangslot[] = [];
  for (const lot of tilgangslots) {
    if (atSaelge <= TOLERANCE) {
      resterendeLots.push(lot);
      continue;
    }
    const solgtFraLot = Math.min(atSaelge, lot.antal);
    kostbasisSolgt += solgtFraLot * lot.kurs;
    atSaelge -= solgtFraLot;
    const rest = lot.antal - solgtFraLot;
    if (rest > TOLERANCE) {
      resterendeLots.push({ antal: rest, kurs: lot.kurs });
    }
  }

  if (atSaelge > TOLERANCE) {
    throw new Error(
      `Kan ikke fordele afgang på beholdningen: ${atSaelge} stk mangler basis (Primo + Tilgange er mindre end Afgange).`
    );
  }

  return { kostbasisSolgt, resterendePrimoAntal, resterendeLots };
}

export function beregnForPapir(gruppe: Transaktion[]): PapirBeregning {
  const papirId = gruppe[0].papirId;
  const papirnavn = gruppe[0].papirnavn;
  const isin = gruppe[0].isin;

  const [primoAntal, primoVaerdi, primoKurs] = vaegtetLinje(gruppe, "primo");
  const [tilgangAntal, tilgangBeloeb] = vaegtetLinje(gruppe, "tilgang");
  const [afgangAntal, afgangBeloeb] = vaegtetLinje(gruppe, "afgang");
  const [ultimoAntal, ultimoVaerdi, ultimoKurs] = vaegtetLinje(gruppe, "ultimo");

  if (!gruppe.some((l) => l.type === "ultimo")) {
    throw new Error(`'${papirnavn}' mangler en Ultimo-linje — kan ikke beregnes.`);
  }

  const tilgangslots = byggTilgangslots(gruppe);
  const { kostbasisSolgt, resterendePrimoAntal, resterendeLots } = fordelFifo(
    primoAntal,
    primoKurs,
    tilgangslots,
    afgangAntal
  );

  const kostbasisResterende =
    resterendePrimoAntal * primoKurs + resterendeLots.reduce((s, l) => s + l.antal * l.kurs, 0);

  const realiseret = afgangBeloeb - kostbasisSolgt;
  const urealiseret = ultimoVaerdi - kostbasisResterende;

  const kontrolsum = ultimoVaerdi + afgangBeloeb - primoVaerdi - tilgangBeloeb;
  const kontrolsumDiff = kontrolsum - (realiseret + urealiseret);
  if (Math.abs(kontrolsumDiff) > 0.01) {
    throw new Error(
      `Kontrolsum stemmer ikke for '${papirnavn}': forventede ${kontrolsum.toFixed(2)}, fik ${(realiseret + urealiseret).toFixed(2)}.`
    );
  }

  return {
    papirId,
    papirnavn,
    isin,
    primoAntal,
    primoKurs,
    primoVaerdi,
    tilgangAntal,
    tilgangBeloeb,
    afgangAntal,
    afgangBeloeb,
    ultimoAntal,
    ultimoKurs,
    ultimoVaerdi,
    realiseret,
    urealiseret,
    kontrolsumDiff,
  };
}

export function beregnAlle(data: Transaktion[]): PapirBeregning[] {
  return Array.from(grupperPrPapir(data).values()).map(beregnForPapir);
}
