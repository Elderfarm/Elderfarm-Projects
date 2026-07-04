"use client";

import { useMemo, useRef, useState } from "react";
import { Button } from "@/components/ui/Button";
import { Badge } from "@/components/ui/Badge";
import { Callout } from "@/components/ui/Callout";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Input, Label } from "@/components/ui/Input";
import { StatCard } from "@/components/ui/StatCard";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/Table";
import { UdbytteTabel, type UdbytteRaekke } from "@/components/udbytte/UdbytteTabel";
import {
  beregnAlleUdbytter,
  harFejl,
  opsummerUdbytter,
  parseBeloeb,
  validerUdbytte,
  type UdbytteLinje,
  type UdbytteResultat,
} from "@/lib/calculations/udbytte";
import { byggUdbytteLinjer, genererCsv } from "@/lib/csv/economic";
import { importerUdbytteFil } from "@/lib/import/udbytteImport";
import { hasSupabaseEnv } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/client";

const EKSEMPEL_RAEKKE: UdbytteRaekke = {
  papirnavn: "Novo Nordisk",
  land: "Danmark",
  beloebstype: "netto",
  beloeb: "18823.41",
  dato: "2024-03-26",
};

function tilLinje(r: UdbytteRaekke): UdbytteLinje {
  return {
    papirnavn: r.papirnavn.trim(),
    land: r.land,
    beloebstype: r.beloebstype,
    beloeb: parseBeloeb(r.beloeb),
    dato: r.dato || null,
  };
}

function erUdfyldt(r: UdbytteRaekke): boolean {
  return r.papirnavn.trim() !== "" || r.beloeb.trim() !== "";
}

function formatKr(v: number): string {
  return `${v.toLocaleString("da-DK", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} kr.`;
}

export default function UdbyttePage() {
  const [raekker, setRaekker] = useState<UdbytteRaekke[]>([EKSEMPEL_RAEKKE]);
  const [resultater, setResultater] = useState<UdbytteResultat[] | null>(null);
  const [gemStatus, setGemStatus] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const [resultatkonto, setResultatkonto] = useState("2100");
  const [bankkonto, setBankkonto] = useState("5820");
  const [danskSkattekonto, setDanskSkattekonto] = useState("6210");
  const [udenlandskSkattekonto, setUdenlandskSkattekonto] = useState("6220");

  const linjer = useMemo(() => raekker.filter(erUdfyldt).map(tilLinje), [raekker]);
  const fund = useMemo(() => validerUdbytte(linjer), [linjer]);
  const blokeret = harFejl(fund);

  async function handleFilUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const fil = e.target.files?.[0];
    if (!fil) return;
    try {
      const importeret = await importerUdbytteFil(fil);
      if (importeret.length === 0) {
        setGemStatus("Filen indeholdt ingen genkendelige rækker.");
      } else {
        setRaekker(importeret);
        setResultater(null);
      }
    } catch (err) {
      setGemStatus(`Kunne ikke læse filen: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  function beregn() {
    setResultater(beregnAlleUdbytter(linjer));
    setGemStatus(null);
  }

  async function gemBeregning() {
    if (!resultater) return;
    if (!hasSupabaseEnv()) {
      setGemStatus("Supabase er ikke sat op endnu — beregningen er ikke gemt.");
      return;
    }
    try {
      const supabase = createClient();
      const { data: userData } = await supabase.auth.getUser();
      if (!userData.user) {
        setGemStatus("Du skal være logget ind for at gemme.");
        return;
      }
      const { data: profil } = await supabase
        .from("profiles")
        .select("company_id")
        .eq("id", userData.user.id)
        .maybeSingle();
      if (!profil) {
        setGemStatus("Fandt ingen virksomhed knyttet til din bruger.");
        return;
      }
      const { error } = await supabase.from("dividends").insert(
        resultater.map((r) => ({
          company_id: profil.company_id,
          security_name: r.papirnavn,
          country_code: r.landekode,
          payment_date: r.dato,
          amount: r.nettoUdbytte,
          amount_type: "netto",
          gross_amount: r.bruttoUdbytte,
          net_amount: r.nettoUdbytte,
          withholding_tax: r.kildeskat,
          is_domestic: r.erDansk,
          created_by: userData.user.id,
        }))
      );
      if (error) throw error;
      setGemStatus("Beregningen er gemt.");
    } catch (err) {
      setGemStatus(`Kunne ikke gemme: ${err instanceof Error ? err.message : String(err)}`);
    }
  }

  const opsummering = resultater ? opsummerUdbytter(resultater) : null;
  const kladdeLinjer = resultater
    ? byggUdbytteLinjer(resultater, { resultatkonto, bankkonto, danskSkattekonto, udenlandskSkattekonto })
    : [];

  function downloadCsv() {
    const csv = genererCsv(kladdeLinjer);
    const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "udbytte_kassekladde.csv";
    a.click();
    URL.revokeObjectURL(url);
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">💰 Udbytte</h1>
        <p className="mt-1 text-sm text-muted">
          Regner ud, hvor meget der egentlig blev udloddet i udbytte (bruttobeløbet) og hvor meget
          der blev trukket i skat, uanset om I kender netto- eller bruttobeløbet.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>1. Indtast jeres udbytter</CardTitle>
          <CardDescription>
            Skriv direkte i tabellen — I kan angive ENTEN netto- eller bruttobeløbet. Har I mange
            linjer, kan I i stedet uploade en Excel- eller CSV-fil.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <UdbytteTabel raekker={raekker} onChange={setRaekker} />
          <div className="flex items-center gap-3">
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
        </CardHeader>
        <CardContent>
          {fund.length === 0 ? (
            <Callout tone="success">✅ Alt ser fint ud — ingen fejl eller advarsler.</Callout>
          ) : (
            <div className="space-y-3">
              <Table>
                <Thead>
                  <Tr>
                    <Th>Række</Th>
                    <Th>Papir</Th>
                    <Th>Status</Th>
                    <Th>Besked</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {fund.map((f, i) => (
                    <Tr key={i}>
                      <Td>{f.raekke}</Td>
                      <Td>{f.papirnavn}</Td>
                      <Td>
                        <Badge status={f.niveau === "fejl" ? "danger" : "warning"}>
                          {f.niveau === "fejl" ? "Fejl" : "Advarsel"}
                        </Badge>
                      </Td>
                      <Td>{f.besked}</Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
              {blokeret ? (
                <Callout tone="danger">🚫 Ret fejlene i tabellen ovenfor før I kan beregne.</Callout>
              ) : (
                <Callout tone="warning">Der er kun advarsler — I kan godt beregne, men tjek dem gerne først.</Callout>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>3. Beregn bruttoudbytte og kildeskat</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <Button onClick={beregn} disabled={blokeret || linjer.length === 0}>
            Beregn
          </Button>

          {resultater && opsummering && (
            <>
              <Table>
                <Thead>
                  <Tr>
                    <Th>Papir</Th>
                    <Th>Dato</Th>
                    <Th>Land</Th>
                    <Th className="text-right">Nettoudbytte</Th>
                    <Th className="text-right">Bruttoudbytte</Th>
                    <Th className="text-right">Kildeskat</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {resultater.map((r, i) => (
                    <Tr key={i}>
                      <Td>{r.papirnavn}</Td>
                      <Td>{r.dato ?? "–"}</Td>
                      <Td>{r.landnavn}</Td>
                      <Td className="text-right">{formatKr(r.nettoUdbytte)}</Td>
                      <Td className="text-right">{formatKr(r.bruttoUdbytte)}</Td>
                      <Td className="text-right">{formatKr(r.kildeskat)}</Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
                <StatCard label="Dansk udbytte, brutto" value={formatKr(opsummering.danskBrutto)} />
                <StatCard label="Udenlandsk udbytte, brutto" value={formatKr(opsummering.udenlandskBrutto)} />
                <StatCard label="I alt modtaget (netto)" value={formatKr(opsummering.nettoIAlt)} />
              </div>

              <Button variant="secondary" onClick={gemBeregning}>
                Gem beregning
              </Button>
              {gemStatus && <Callout tone="info">{gemStatus}</Callout>}
            </>
          )}
        </CardContent>
      </Card>

      {resultater && (
        <Card>
          <CardHeader>
            <CardTitle>4. Hent fil til e-conomic</CardTitle>
            <CardDescription>
              Bruttoudbyttet bogføres som indtægt. Kildeskatten bogføres som et tilgodehavende
              (dansk kildeskat kan modregnes/tilbagesøges i Danmark, hjemlandet). Nettobeløbet er
              det, der allerede står på jeres bankkonto.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div>
                <Label htmlFor="resultatkonto">Konto til udbytteindtægt (drift)</Label>
                <Input id="resultatkonto" value={resultatkonto} onChange={(e) => setResultatkonto(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="dansk-skat">Konto til tilgodehavende udbytteskat, Danmark</Label>
                <Input id="dansk-skat" value={danskSkattekonto} onChange={(e) => setDanskSkattekonto(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="bankkonto">Bankkonto</Label>
                <Input id="bankkonto" value={bankkonto} onChange={(e) => setBankkonto(e.target.value)} />
              </div>
              <div>
                <Label htmlFor="udl-skat">Konto til tilgodehavende udbytteskat, udenlandsk</Label>
                <Input id="udl-skat" value={udenlandskSkattekonto} onChange={(e) => setUdenlandskSkattekonto(e.target.value)} />
              </div>
            </div>

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
          </CardContent>
        </Card>
      )}
    </div>
  );
}
