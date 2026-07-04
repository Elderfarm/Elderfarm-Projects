import { beregnAlleUdbytter, opsummerUdbytter, validerUdbytte, type UdbytteLinje } from "../src/lib/calculations/udbytte";

const linjer: UdbytteLinje[] = [
  { papirnavn: "Novo Nordisk", land: "Danmark", beloebstype: "netto", beloeb: 18823.41, dato: "2024-03-26" },
  { papirnavn: "Volvo B", land: "Sverige", beloebstype: "brutto", beloeb: 57823.2, dato: "2024-04-05" },
  { papirnavn: "Taiwan Semiconductor", land: "USA", beloebstype: "netto", beloeb: 19489.99, dato: "2024-05-15" },
];

const fund = validerUdbytte(linjer);
console.log("fund:", fund);

const resultater = beregnAlleUdbytter(linjer);
console.table(resultater);

console.log("opsummering:", opsummerUdbytter(resultater));

// Forventede facit-tal (verificeret mod Python-versionen og den rigtige skabelon):
const forventet = {
  novoBrutto: 24132.58,
  novoSkat: 5309.17,
  volvoNetto: 49149.72,
  volvoSkat: 8673.48,
  taiwanBrutto: 22929.4,
};

function tjek(navn: string, faktisk: number, forventetVal: number) {
  const ok = Math.abs(faktisk - forventetVal) < 0.01;
  console.log(`${ok ? "OK " : "FEJL"} ${navn}: ${faktisk.toFixed(2)} (forventet ${forventetVal})`);
  if (!ok) process.exitCode = 1;
}

tjek("Novo Nordisk brutto", resultater[0].bruttoUdbytte, forventet.novoBrutto);
tjek("Novo Nordisk kildeskat", resultater[0].kildeskat, forventet.novoSkat);
tjek("Volvo B netto", resultater[1].nettoUdbytte, forventet.volvoNetto);
tjek("Volvo B kildeskat", resultater[1].kildeskat, forventet.volvoSkat);
tjek("Taiwan Semiconductor brutto", resultater[2].bruttoUdbytte, forventet.taiwanBrutto);
