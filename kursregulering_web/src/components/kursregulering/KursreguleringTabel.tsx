"use client";

import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Input";
import type { TransaktionType } from "@/lib/calculations/kursregulering";

export interface KursreguleringRaekke {
  papirnavn: string;
  isin: string;
  type: TransaktionType | "";
  dato: string;
  antal: string;
  kurs: string;
}

const TYPE_LABELS: Record<TransaktionType, string> = {
  primo: "Primo",
  tilgang: "Tilgang",
  afgang: "Afgang",
  ultimo: "Ultimo",
};

interface Props {
  raekker: KursreguleringRaekke[];
  onChange: (raekker: KursreguleringRaekke[]) => void;
}

export function KursreguleringTabel({ raekker, onChange }: Props) {
  function opdaterRaekke(index: number, felter: Partial<KursreguleringRaekke>) {
    const nye = raekker.slice();
    nye[index] = { ...nye[index], ...felter };
    onChange(nye);
  }

  function tilfoejRaekke() {
    onChange([...raekker, { papirnavn: "", isin: "", type: "tilgang", dato: "", antal: "", kurs: "" }]);
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
              <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted">Type</th>
              <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted">Dato</th>
              <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted">Antal</th>
              <th className="px-3 py-2.5 text-xs font-semibold uppercase tracking-wide text-muted">Kurs</th>
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
                    placeholder="Fx Novo Nordisk B"
                    onChange={(e) => opdaterRaekke(index, { papirnavn: e.target.value })}
                  />
                </td>
                <td className="p-2">
                  <Select
                    className="h-9"
                    value={raekke.type}
                    onChange={(e) => opdaterRaekke(index, { type: e.target.value as TransaktionType })}
                  >
                    {Object.entries(TYPE_LABELS).map(([v, label]) => (
                      <option key={v} value={v}>
                        {label}
                      </option>
                    ))}
                  </Select>
                </td>
                <td className="p-2">
                  <input
                    type="date"
                    className="h-9 w-full rounded-lg border border-border px-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    value={raekke.dato}
                    onChange={(e) => opdaterRaekke(index, { dato: e.target.value })}
                  />
                </td>
                <td className="p-2">
                  <input
                    type="number"
                    step="1"
                    className="h-9 w-full rounded-lg border border-border px-2 text-right text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    value={raekke.antal}
                    placeholder="0"
                    onChange={(e) => opdaterRaekke(index, { antal: e.target.value })}
                  />
                </td>
                <td className="p-2">
                  <input
                    type="number"
                    step="0.01"
                    className="h-9 w-full rounded-lg border border-border px-2 text-right text-sm focus:outline-none focus:ring-2 focus:ring-primary/30"
                    value={raekke.kurs}
                    placeholder="0,00"
                    onChange={(e) => opdaterRaekke(index, { kurs: e.target.value })}
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
