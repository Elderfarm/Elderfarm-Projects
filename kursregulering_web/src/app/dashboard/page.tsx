import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Callout } from "@/components/ui/Callout";
import { StatCard } from "@/components/ui/StatCard";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/Table";
import { hasSupabaseEnv } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";

interface Kpier {
  samletUdbytteskat: number;
  samletKursregulering: number;
  samletSkatteeffekt: number;
  antalInvesteringer: number;
  antalEksporteredePosteringer: number;
}

interface SenesteBeregning {
  type: "Udbytte" | "Kursregulering";
  papirnavn: string;
  beloeb: number;
  dato: string;
}

function formatKr(v: number): string {
  return `${v.toLocaleString("da-DK", { minimumFractionDigits: 0, maximumFractionDigits: 0 })} kr.`;
}

async function hentDashboardData(): Promise<{ kpier: Kpier; seneste: SenesteBeregning[] } | null> {
  if (!hasSupabaseEnv()) return null;

  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return null;

    const { data: profil } = await supabase
      .from("profiles")
      .select("company_id")
      .eq("id", user.id)
      .maybeSingle();
    if (!profil) return null;

    const [{ data: udbytter }, { data: kursreguleringer }, { data: eksporter }] = await Promise.all([
      supabase
        .from("dividends")
        .select("security_name, withholding_tax, gross_amount, payment_date, created_at")
        .eq("company_id", profil.company_id)
        .order("created_at", { ascending: false }),
      supabase
        .from("price_regulations")
        .select("security_name, realized_gain, unrealized_gain, year, created_at")
        .eq("company_id", profil.company_id)
        .order("created_at", { ascending: false }),
      supabase.from("exports").select("row_count").eq("company_id", profil.company_id),
    ]);

    const samletUdbytteskat = (udbytter ?? []).reduce((s, r) => s + Number(r.withholding_tax ?? 0), 0);
    const samletKursregulering = (kursreguleringer ?? []).reduce(
      (s, r) => s + Number(r.realized_gain ?? 0) + Number(r.unrealized_gain ?? 0),
      0
    );
    const papirer = new Set([
      ...(udbytter ?? []).map((r) => r.security_name),
      ...(kursreguleringer ?? []).map((r) => r.security_name),
    ]);

    const seneste: SenesteBeregning[] = [
      ...(udbytter ?? []).slice(0, 5).map((r) => ({
        type: "Udbytte" as const,
        papirnavn: r.security_name,
        beloeb: Number(r.gross_amount ?? 0),
        dato: r.payment_date ?? r.created_at,
      })),
      ...(kursreguleringer ?? []).slice(0, 5).map((r) => ({
        type: "Kursregulering" as const,
        papirnavn: r.security_name,
        beloeb: Number(r.realized_gain ?? 0) + Number(r.unrealized_gain ?? 0),
        dato: String(r.year),
      })),
    ]
      .sort((a, b) => (a.dato < b.dato ? 1 : -1))
      .slice(0, 8);

    return {
      kpier: {
        samletUdbytteskat,
        samletKursregulering,
        samletSkatteeffekt: samletUdbytteskat + samletKursregulering,
        antalInvesteringer: papirer.size,
        antalEksporteredePosteringer: (eksporter ?? []).reduce((s, r) => s + Number(r.row_count ?? 0), 0),
      },
      seneste,
    };
  } catch {
    return null;
  }
}

export default async function DashboardPage() {
  const resultat = await hentDashboardData();

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">Dashboard</h1>
        <p className="mt-1 text-sm text-muted">Overblik over jeres udbytte- og kursreguleringsberegninger.</p>
      </div>

      {!resultat && (
        <Callout tone="info">
          Ingen data at vise endnu. {hasSupabaseEnv() ? "Log ind og gem en beregning i Udbytte eller Kursregulering." : "Forbind Supabase for at se rigtige tal her (se README.md)."}
        </Callout>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label="Samlet udbytteskat" value={formatKr(resultat?.kpier.samletUdbytteskat ?? 0)} />
        <StatCard label="Samlet kursregulering" value={formatKr(resultat?.kpier.samletKursregulering ?? 0)} />
        <StatCard label="Samlet skatteeffekt" value={formatKr(resultat?.kpier.samletSkatteeffekt ?? 0)} hint="Udbytteskat + kursregulering" />
        <StatCard label="Behandlede investeringer" value={String(resultat?.kpier.antalInvesteringer ?? 0)} />
        <StatCard label="Eksporterede posteringer" value={String(resultat?.kpier.antalEksporteredePosteringer ?? 0)} />
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Seneste beregninger</CardTitle>
          </CardHeader>
          <CardContent>
            {resultat && resultat.seneste.length > 0 ? (
              <Table>
                <Thead>
                  <Tr>
                    <Th>Type</Th>
                    <Th>Papir</Th>
                    <Th>Dato/år</Th>
                    <Th className="text-right">Beløb</Th>
                  </Tr>
                </Thead>
                <Tbody>
                  {resultat.seneste.map((r, i) => (
                    <Tr key={i}>
                      <Td>{r.type}</Td>
                      <Td>{r.papirnavn}</Td>
                      <Td>{r.dato}</Td>
                      <Td className="text-right">{formatKr(r.beloeb)}</Td>
                    </Tr>
                  ))}
                </Tbody>
              </Table>
            ) : (
              <p className="text-sm text-muted">Ingen beregninger gemt endnu.</p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Hurtig adgang</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-col gap-2">
            <Link href="/dashboard/udbytte" className="rounded-xl bg-muted-subtle px-4 py-3 text-sm font-medium text-foreground hover:bg-slate-200">
              💰 Ny udbytteberegning
            </Link>
            <Link href="/dashboard/kursregulering" className="rounded-xl bg-muted-subtle px-4 py-3 text-sm font-medium text-foreground hover:bg-slate-200">
              📈 Ny kursregulering
            </Link>
            <Link href="/dashboard/eksporter" className="rounded-xl bg-muted-subtle px-4 py-3 text-sm font-medium text-foreground hover:bg-slate-200">
              📤 Se eksporter
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
