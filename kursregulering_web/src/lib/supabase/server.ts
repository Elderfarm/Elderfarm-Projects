import { createServerClient } from "@supabase/ssr";
import { cookies } from "next/headers";

/**
 * Supabase-klient til brug i Server Components, Server Actions og Route
 * Handlers. Læser/skriver auth-cookies via Next.js' cookies()-API.
 */
export async function createClient() {
  const cookieStore = await cookies();

  return createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return cookieStore.getAll();
        },
        setAll(cookiesToSet) {
          try {
            cookiesToSet.forEach(({ name, value, options }) =>
              cookieStore.set(name, value, options)
            );
          } catch {
            // Kaldes fra en Server Component uden write-adgang til cookies —
            // det er OK, så længe proxy.ts opdaterer sessionen på request-niveau.
          }
        },
      },
    }
  );
}
