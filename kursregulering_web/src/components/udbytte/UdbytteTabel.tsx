"use client";

import { LANDE_NAVNE } from "@/lib/calculations/udbytte";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Input";

export interface UdbytteRaekke {
  papirnavn: string;
  land: string;
  beloebstype: "netto" | "brutto";
  beloeb: string;
  dato: string; // ISO eller ""
}

const LANDE_MULIGHEDER = Object.values(LANDE_NAVNE).sort((a, b) => a.localeCompare(b, "da"));

interface Props {
  raekker: UdbytteRaekke[];
  onChange: (raekker: UdbytteRaekke[]) => void;
}

export function UdbytteTabel({ raekker, onChange }: Props) {
  function opdaterRaekke(index: number, felter: Partial<UdbytteRaekke>) {
    const nye = raekker.slice();
    nye[index] = { ...nye[index], ...felter };
    onChange(nye);
  }

  function tilfoejRaekke() {
    onChange([...raekker, { papirnavn: "", land: "Danmark", beloebstype: "netto", beloeb: "", dato: "" }]);
  }

  function fjernRaekke(index: number) {
    onChange(raekker.filter((_, i) => i !== index));
  }

  return (
    <div className="space-y-3">
      <div className="overflow-x-auto rounded-xl border border-border">
        <table className="w-full text-left text-sm">
          <thead className="bg-muted-subtle">
            <tr>
              <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted">Papir</th>
              <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted">Land</th>
              <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted">Type</th>
              <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted">Beløb (kr.)</th>
              <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted">Dato</th>
              <th className="w-10" />
            </tr>
          </thead>
          <tbody className="divide-y divide-border">
            {raekker.map((raekke, index) => (
              <tr key={index}>
                <td className="p-2">
                  <input
                    className="h-9 w-full rounded-lg border border-border px-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    value={raekke.papirnavn}
                    placeholder="Fx Novo Nordisk"
                    onChange={(e) => opdaterRaekke(index, { papirnavn: e.target.value })}
                  />
                </td>
                <td className="p-2">
                  <Select
                    className="h-9"
                    value={raekke.land}
                    onChange={(e) => opdaterRaekke(index, { land: e.target.value })}
                  >
                    {LANDE_MULIGHEDER.map((land) => (
                      <option key={land} value={land}>
                        {land}
                      </option>
                    ))}
                  </Select>
                </td>
                <td className="p-2">
                  <Select
                    className="h-9"
                    value={raekke.beloebstype}
                    onChange={(e) => opdaterRaekke(index, { beloebstype: e.target.value as "netto" | "brutto" })}
                  >
                    <option value="netto">Netto</option>
                    <option value="brutto">Brutto</option>
                  </Select>
                </td>
                <td className="p-2">
                  <input
                    type="number"
                    step="0.01"
                    className="h-9 w-full rounded-lg border border-border px-2 text-right text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    value={raekke.beloeb}
                    placeholder="0,00"
                    onChange={(e) => opdaterRaekke(index, { beloeb: e.target.value })}
                  />
                </td>
                <td className="p-2">
                  <input
                    type="date"
                    className="h-9 w-full rounded-lg border border-border px-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    value={raekke.dato}
                    onChange={(e) => opdaterRaekke(index, { dato: e.target.value })}
                  />
                </td>
                <td className="p-2 text-center">
                  <button
                    type="button"
                    onClick={() => fjernRaekke(index)}
                    className="text-muted hover:text-danger"
                    aria-label="Fjern linje"
                  >
                    ✕
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <Button variant="secondary" size="sm" onClick={tilfoejRaekke}>
        + Tilføj linje
      </Button>
    </div>
  );
}
