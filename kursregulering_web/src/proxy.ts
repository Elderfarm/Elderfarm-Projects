import { createServerClient } from "@supabase/ssr";
import { NextResponse, type NextRequest } from "next/server";
import { hasSupabaseEnv } from "@/lib/supabase/config";

/**
 * Next.js 16 har omdøbt middleware.ts -> proxy.ts (samme funktion, nyt navn).
 * Opdaterer Supabase-sessionen på hvert request, og sender uautoriserede
 * brugere til /login. Se node_modules/next/dist/docs/01-app for detaljer.
 *
 * VIGTIGT: Hvis Supabase-miljøvariablerne ikke er sat endnu, lukker vi
 * requests igennem uden login-tjek (i stedet for at crashe), så appen kan
 * bygges og gennemses før et rigtigt Supabase-projekt er koblet på. Sæt
 * NEXT_PUBLIC_SUPABASE_URL/ANON_KEY (se .env.local.example) før produktion —
 * uden dem er dashboardet reelt IKKE adgangsbeskyttet.
 */
export async function proxy(request: NextRequest) {
  if (!hasSupabaseEnv()) {
    return NextResponse.next();
  }

  let response = NextResponse.next({ request });

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll();
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) => request.cookies.set(name, value));
          response = NextResponse.next({ request });
          cookiesToSet.forEach(({ name, value, options }) =>
            response.cookies.set(name, value, options)
          );
        },
      },
    }
  );

  const { data } = await supabase.auth.getUser();
  const erDashboardRute = request.nextUrl.pathname.startsWith("/dashboard");

  if (erDashboardRute && !data.user) {
    const loginUrl = new URL("/login", request.url);
    loginUrl.searchParams.set("naeste", request.nextUrl.pathname);
    return NextResponse.redirect(loginUrl);
  }

  return response;
}

export const config = {
  matcher: ["/dashboard/:path*"],
};
