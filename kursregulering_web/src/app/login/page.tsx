import { Suspense } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Callout } from "@/components/ui/Callout";
import { LoginForm } from "@/components/auth/LoginForm";
import { hasSupabaseEnv } from "@/lib/supabase/config";

export default function LoginPage() {
  return (
    <div className="flex min-h-screen flex-1 items-center justify-center bg-muted-subtle/40 px-4">
      <Card className="w-full max-w-sm p-2">
        <CardHeader>
          <div className="mb-2 text-2xl">💹</div>
          <CardTitle>Log ind</CardTitle>
          <CardDescription>Aktier &amp; Udbytte — beregning og bogføring</CardDescription>
        </CardHeader>
        <CardContent>
          {hasSupabaseEnv() ? (
            <Suspense>
              <LoginForm />
            </Suspense>
          ) : (
            <Callout tone="warning">
              Supabase er ikke sat op endnu. Tilføj NEXT_PUBLIC_SUPABASE_URL og
              NEXT_PUBLIC_SUPABASE_ANON_KEY i .env.local — se README.md.
            </Callout>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
