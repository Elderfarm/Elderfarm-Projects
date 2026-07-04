/**
 * Om Supabase-miljøvariablerne er sat. Bruges til at vise en pæn
 * "opsætning mangler"-besked i stedet for at crashe, indtil et rigtigt
 * Supabase-projekt er koblet på (se .env.local.example).
 */
export function hasSupabaseEnv(): boolean {
  return Boolean(
    process.env.NEXT_PUBLIC_SUPABASE_URL && process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY
  );
}
