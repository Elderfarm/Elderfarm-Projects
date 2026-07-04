"use client";

import { useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Badge, type BadgeStatus } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Input, Label } from "@/components/ui/Input";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/Table";
import { KursreguleringTabel, type KursreguleringRaekke } from "@/components/kursregulering/KursreguleringTabel";
import { KursreguleringGuide } from "@/components/kursregulering/KursreguleringGuide";
import {
  beregnAlle,
  harFejl,
  opsummerPrPapir,
  validerTransaktioner,
  type PapirBeregning,
  type Transaktion,
} from "@/lib/calculations/kursregulering";
import { byggKursreguleringLinjer, genererCsv } from "@/lib/csv/economic";
import { importerKursreguleringFil } from "@/lib/import/kursreguleringImport";

const EKSEMPEL_RAEKKER: KursreguleringRaekke[] = [
  { papirnavn: "Novo Nordisk B", isin: "DK0060534915", type: "primo", dato: "2024-01-01", antal: "100", kurs: "700" },
  { papirnavn: "Novo Nordisk B", isin: "DK0060534915", type: "tilgang", dato: "2024-03-15", antal: "50", kurs: "800" },
  { papirnavn: "Novo Nordisk B", isin: "DK0060534915", type: "afgang", dato: "2024-09-10", antal: "30", kurs: "900" },
  { papirnavn: "Novo Nordisk B", isin: "DK0060534915", type: "ultimo", dato: "2024-12-31", antal: "120", kurs: "850" },
];

function tilTal(v: string): number | null {
  if (v.trim() === "") return null;
  const tal = Number(v);
  return Number.isFinite(tal) ? tal : null;
}

function tilTransaktioner(raekker: KursreguleringRaekke[]): Transaktion[] {
  return raekker
    .filter((r) => r.papirnavn.trim() !== "" || r.antal.trim() !== "")
    .map((r, index) => {
      const antal = tilTal(r.antal);
      const kurs = tilTal(r.kurs);
      return {
        raekke: index + 1,
        papirId: r.isin.trim() || r.papirnavn.trim(),
        papirnavn: r.papirnavn.trim() || r.isin.trim(),
        isin: r.isin.trim(),
        type: (r.type || "tilgang") as Transaktion["type"],
        dato: r.dato || null,
        antal,
        kurs,
        beloeb: antal !== null && kurs !== null ? antal * kurs : null,
      };
    });
}

function formatKr(v: number): string {
  return `${v.toLocaleString("da-DK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kr.`;
}

function badgeStatus(status: "OK" | "Advarsel" | "Fejl"): BadgeStatus {
  if (status === "Fejl") return "danger";
  if (status === "Advarsel") return "warning";
  return "success";
}

function tomRaekke(): KursreguleringRaekke {
  return { papirnavn: "", isin: "", type: "tilgang", dato: "", antal: "", kurs: "" };
}

export default function KursreguleringPage() {
  const [raekker, setRaekker] = useState<KursreguleringRaekke[]>(EKSEMPEL_RAEKKER);
  const [resultater, setResultater] = useState<PapirBeregning[] | null>(null);
  const [beregningsFejl, setBeregningsFejl] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [resultatkonto, setResultatkonto] = useState("7220");
  const [balancekonto, setBalancekonto] = useState("6820");
  const [bogfoeringsdato, setBogfoeringsdato] = useState(new Date().toISOString().slice(0, 10));

  const data = useMemo(() => tilTransaktioner(raekker), [raekker]);
  const fund = useMemo(() => validerTransaktioner(data), [data]);
  const oversigt = useMemo(() => opsummerPrPapir(data, fund), [data, fund]);
  const blokeret = harFejl(fund);

  async function handleFilUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const fil = e.target.files?.[0];
    if (!fil) return;
    try {
      const importeret = await importerKursreguleringFil(fil);
      setRaekker(importeret);
      setResultater(null);
    } catch (err) {
      setBeregningsFejl(`Kunne ikke læse filen: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function beregn() {
    try {
      setResultater(beregnAlle(data));
      setBeregningsFejl(null);
    } catch (err) {
      setBeregningsFejl(err instanceof Error ? err.message : String(err));
      setResultater(null);
    }
  }

  const kladdeLinjer = resultater
    ? byggKursreguleringLinjer(resultater, { resultatkonto, balancekonto, bogfoeringsdato })
    : [];

  function downloadCsv() {
    const csv = genererCsv(kladdeLinjer);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `kursregulering_kassekladde_${bogfoeringsdato}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">📈 Kursregulering</h1>
        <p className="mt-1 text-sm text-muted">
          Regner ud, hvor meget I skal beskattes af, fordi jeres aktier er steget eller faldet i
          værdi i år (lagerprincippet). Gælder kun noterede aktier.
        </p>
      </div>

      <KursreguleringGuide />

      <Card>
        <CardHeader>
          <CardTitle>1. Indtast jeres køb/salg</CardTitle>
          <CardDescription>
            Én linje pr. handling: Primo (start af året), Tilgang (køb), Afgang (salg), Ultimo
            (slut af året). Har I mange linjer, kan I i stedet uploade en Excel- eller CSV-fil.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <KursreguleringTabel raekker={raekker} onChange={setRaekker} />
          <div className="flex flex-wrap items-center gap-3">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => {
                setRaekker(EKSEMPEL_RAEKKER.map((r) => ({ ...r })));
                setResultater(null);
              }}
            >
              📖 Indlæs eksempel
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setRaekker([tomRaekke()]);
                setResultater(null);
              }}
            >
              Ryd tabel
            </Button>
            <input
              ref={fileInputRef}
              type="file"
              accept=".xlsx,.xls,.csv"
              onChange={handleFilUpload}
              className="text-sm text-muted file:mr-3 file:rounded-lg file:border-0 file:bg-muted-subtle file:px-3 file:py-2 file:text-sm file:font-medium hover:file:bg-slate-200"
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>2. Tjek af data</CardTitle>
          <CardDescription>Vi tjekker automatisk, om tallene hænger sammen, før vi regner videre.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Table>
            <Thead>
              <Tr>
                <Th>Papir</Th>
                <Th>ISIN</Th>
                <Th>Status</Th>
                <Th>Antal fejl</Th>
                <Th>Antal advarsler</Th>
              </Tr>
            </Thead>
            <Tbody>
              {oversigt.map((o) => (
                <Tr key={o.papirId}>
                  <Td>{o.papirnavn}</Td>
                  <Td>{o.isin}</Td>
                  <Td>
                    <Badge status={badgeStatus(o.status)}>{o.status}</Badge>
                  </Td>
                  <Td>{o.antalFejl}</Td>
                  <Td>{o.antalAdvarsler}</Td>
                </Tr>
              ))}
            </Tbody>
          </Table>

          {fund.length > 0 && (
            <Table>
              <Thead>
                <Tr>
                  <Th>Papir</Th>
                  <Th>Status</Th>
                  <Th>Kategori</Th>
                  <Th>Besked</Th>
                </Tr>
              </Thead>
              <Tbody>
                {fund.map((f, i) => (
                  <Tr key={i}>
                    <Td>{f.papirnavn}</Td>
                    <Td>
                      <Badge status={f.niveau === "fejl" ? "danger" : "warning"}>
                        {f.niveau === "fejl" ? "Fejl" : "Advarsel"}
                      </Badge>
                    </Td>
                    <Td>{f.kategori}</Td>
                    <Td>{f.besked}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}

          {blokeret ? (
            <Callout tone="danger">🚫 Der er mindst én fejl, der skal rettes først i tabellen ovenfor.</Callout>
          ) : fund.length > 0 ? (
            <Callout tone="warning">Der er kun advarsler — I kan godt beregne, men tjek dem gerne først.</Callout>
          ) : (
            <Callout tone="success">✅ Alt ser fint ud — ingen fejl eller advarsler.</Callout>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3. Beregn gevinst og tab</CardTitle>
          <CardDescription>
            Værdien ved årets start er allerede beskattet sidste år, så det er kun ændringen i år,
            der beskattes nu. FIFO afgør, hvilke stykker der er solgt fra gammel beholdning, og
            hvilke der er fra årets køb.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button onClick={beregn} disabled={blokeret || data.length === 0}>
            Beregn
          </Button>

          {beregningsFejl && <Callout tone="danger">{beregningsFejl}</Callout>}

          {resultater && (
            <>
              <Table>
                <Thead>
                  <Tr>
                    <Th>Papir</Th>
                    <Th className="text-right">Primo antal</Th>
                    <Th className="text-right">Primo kurs</Th>
                    <Th className="text-right">Primo værdi</Th>
                    <Th className="text-right">Tilgang antal</Th>
                    <Th className="text-right">Tilgang beløb</Th>
                    <Th className="text-right">Afgang antal</Th>
                    <Th className="text-right">Afgang beløb</Th>
                    <Th className="text-right">Ultimo antal</Th>
                    <Th className="text-right">Ultimo kurs</Th>
                    <Th className="text-right">Ultimo værdi</Th>
                    <Th className="text-right">Realiseret</Th>
                    <Th className="text-right">Urealiseret</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {resultater.map((r) => (
                    <Tr key={r.papirId}>
                      <Td>{r.papirnavn}</Td>
                      <Td className="text-right">{r.primoAntal}</Td>
                      <Td className="text-right">{r.primoKurs}</Td>
                      <Td className="text-right">{formatKr(r.primoVaerdi)}</Td>
                      <Td className="text-right">{r.tilgangAntal}</Td>
                      <Td className="text-right">{formatKr(r.tilgangBeloeb)}</Td>
                      <Td className="text-right">{r.afgangAntal}</Td>
                      <Td className="text-right">{formatKr(r.afgangBeloeb)}</Td>
                      <Td className="text-right">{r.ultimoAntal}</Td>
                      <Td className="text-right">{r.ultimoKurs}</Td>
                      <Td className="text-right">{formatKr(r.ultimoVaerdi)}</Td>
                      <Td className="text-right font-medium">{formatKr(r.realiseret)}</Td>
                      <Td className="text-right font-medium">{formatKr(r.urealiseret)}</Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
              <p className="text-xs text-muted">
                Kontroltjek (indbygget): Ultimo værdi + Afgang beløb − Primo værdi − Tilgang beløb = Realiseret + Urealiseret.
                Så I selv kan afstemme tallene, viser vi alle mellemresultaterne — ikke kun facit.
              </p>
            </>
          )}
        </CardContent>
      </Card>

      {resultater && (
        <Card>
          <CardHeader>
            <CardTitle>4. Hent fil til e-conomic</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div>
                <Label htmlFor="resultatkonto">Konto til kursregulering (resultat)</Label>
                <Input id="resultatkonto" value={resultatkonto} onChange={(e) => setResultatkonto(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="balancekonto">Konto til værdipapirer (balance)</Label>
                <Input id="balancekonto" value={balancekonto} onChange={(e) => setBalancekonto(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="bogfoeringsdato">Bogføringsdato</Label>
                <Input id="bogfoeringsdato" type="date" value={bogfoeringsdato} onChange={(e) => setBogfoeringsdato(e.target.value)} />
              </div>
            </div>

            {kladdeLinjer.length === 0 ? (
              <Callout tone="info">Ingen af aktierne har givet gevinst eller tab (alle beløb er 0) — der er ikke noget at hente.</Callout>
            ) : (
              <>
                <Table>
                  <Thead>
                    <Tr>
                      <Th>Bilagsnr.</Th>
                      <Th>Dato</Th>
                      <Th>Konto</Th>
                      <Th className="text-right">Beløb</Th>
                      <Th>Tekst</Th>
                    </Tr>
                  </Thead>
                  <Tbody>
                    {kladdeLinjer.map((l, i) => (
                      <Tr key={i}>
                        <Td>{l.bilagsnr}</Td>
                        <Td>{l.dato}</Td>
                        <Td>{l.konto}</Td>
                        <Td className="text-right">{formatKr(l.beloeb)}</Td>
                        <Td>{l.tekst}</Td>
                      </Tr>
                    ))}
                  </Tbody>
                </Table>
                <Button onClick={downloadCsv}>⬇️ Download CSV til e-conomic</Button>
              </>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
