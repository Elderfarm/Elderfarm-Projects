import { createBrowserClient } from "@supabase/ssr";

/**
 * Supabase-klient til brug i Client Components (browseren).
 * Kræver NEXT_PUBLIC_SUPABASE_URL og NEXT_PUBLIC_SUPABASE_ANON_KEY —
 * se .env.local.example.
 */
export function createClient() {
  return createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!
  );
}
