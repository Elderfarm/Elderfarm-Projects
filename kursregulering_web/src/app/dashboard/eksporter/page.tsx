import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/Card";
import { Callout } from "@/components/ui/Callout";
import { Table, Tbody, Td, Th, Thead, Tr } from "@/components/ui/Table";
import { hasSupabaseEnv } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";

interface EksportRaekke {
  id: string;
  export_type: string;
  file_name: string;
  row_count: number;
  created_at: string;
}

async function hentEksporter(): Promise<EksportRaekke[] | null> {
  if (!hasSupabaseEnv()) return null;
  try {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    if (!user) return null;

    const { data: profil } = await supabase.from("profiles").select("company_id").eq("id", user.id).maybeSingle();
    if (!profil) return null;

    const { data } = await supabase
      .from("exports")
      .select("id, export_type, file_name, row_count, created_at")
      .eq("company_id", profil.company_id)
      .order("created_at", { ascending: false });

    return data ?? [];
  } catch {
    return null;
  }
}

export default async function EksporterPage() {
  const eksporter = await hentEksporter();

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold text-foreground">📤 Eksporter</h1>
        <p className="mt-1 text-sm text-muted">Historik over CSV-filer downloadet til e-conomic.</p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Eksport-historik</CardTitle>
          <CardDescription>
            Downloades en fil fra Udbytte eller Kursregulering, kan den registreres her (kræver Supabase).
          </CardDescription>
        </CardHeader>
        <CardContent>
          {eksporter === null ? (
            <Callout tone="info">
              {hasSupabaseEnv() ? "Log ind for at se jeres eksport-historik." : "Forbind Supabase for at se eksport-historik (se README.md)."}
            </Callout>
          ) : eksporter.length === 0 ? (
            <p className="text-sm text-muted">Ingen eksporter endnu.</p>
          ) : (
            <Table>
              <Thead>
                <Tr>
                  <Th>Type</Th>
                  <Th>Filnavn</Th>
                  <Th className="text-right">Antal rækker</Th>
                  <Th>Dato</Th>
                </Tr>
              </Thead>
              <Tbody>
                {eksporter.map((e) => (
                  <Tr key={e.id}>
                    <Td>{e.export_type === "dividend" ? "Udbytte" : "Kursregulering"}</Td>
                    <Td>{e.file_name}</Td>
                    <Td className="text-right">{e.row_count}</Td>
                    <Td>{new Date(e.created_at).toLocaleDateString("da-DK")}</Td>
                  </Tr>
                ))}
              </Tbody>
            </Table>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
