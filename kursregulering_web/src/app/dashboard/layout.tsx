import type { ReactNode } from "react";
import { Sidebar } from "@/components/layout/Sidebar";
import { Topbar } from "@/components/layout/Topbar";
import { Callout } from "@/components/ui/Callout";
import { hasSupabaseEnv } from "@/lib/supabase/config";
import { createClient } from "@/lib/supabase/server";

interface ProfilRaekke {
  companies: { name: string } | { name: string }[] | null;
}

export default async function DashboardLayout({ children }: { children: ReactNode }) {
  let email: string | null = null;
  let companyName: string | null = null;

  if (hasSupabaseEnv()) {
    const supabase = await createClient();
    const {
      data: { user },
    } = await supabase.auth.getUser();
    email = user?.email ?? null;

    if (user) {
      const { data: profil } = await supabase
        .from("profiles")
        .select("company_id, companies(name)")
        .eq("id", user.id)
        .maybeSingle<ProfilRaekke>();
      const virksomhed = Array.isArray(profil?.companies) ? profil?.companies[0] : profil?.companies;
      companyName = virksomhed?.name ?? null;
    }
  }

  return (
    <div className="flex h-screen">
      <Sidebar />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Topbar email={email} companyName={companyName} />
        <main className="flex-1 overflow-y-auto bg-muted-subtle/40 p-6">
          {!hasSupabaseEnv() && (
            <Callout tone="warning" className="mb-6">
              Supabase er ikke sat op endnu — data gemmes ikke, og denne side er reelt ikke
              login-beskyttet. Se README.md for opsætning.
            </Callout>
          )}
          {children}
        </main>
      </div>
    </div>
  );
}
