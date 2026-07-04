import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/Card";
import { Callout } from "@/components/ui/Callout";
import { SignupForm } from "@/components/auth/SignupForm";
import { hasSupabaseEnv } from "@/lib/supabase/config";

export default function SignupPage() {
  return (
    <div className="flex min-h-screen flex-1 items-center justify-center bg-muted-subtle/40 px-4">
      <Card className="w-full max-w-sm p-2">
        <CardHeader>
          <div className="mb-2 text-2xl">💹</div>
          <CardTitle>Opret konto</CardTitle>
          <CardDescription>Første bruger bliver automatisk admin for jeres virksomhed.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {hasSupabaseEnv() ? (
            <SignupForm />
          ) : (
            <Callout tone="warning">
              Supabase er ikke sat op endnu. Tilføj NEXT_PUBLIC_SUPABASE_URL og
              NEXT_PUBLIC_SUPABASE_ANON_KEY i .env.local — se README.md.
            </Callout>
          )}
          <p className="text-center text-sm text-muted">
            Har I allerede en konto?{" "}
            <Link href="/login" className="font-medium text-primary hover:underline">
              Log ind
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
