"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/cn";

const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: "🏠" },
  { href: "/dashboard/udbytte", label: "Udbytte", icon: "💰" },
  { href: "/dashboard/kursregulering", label: "Kursregulering", icon: "📈" },
  { href: "/dashboard/eksporter", label: "Eksporter", icon: "📤" },
] as const;

export function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="flex h-full w-64 flex-col border-r border-border bg-surface px-4 py-6">
      <div className="mb-8 flex items-center gap-2 px-2">
        <span className="text-2xl">💹</span>
        <span className="text-lg font-semibold text-foreground">Aktier &amp; Udbytte</span>
      </div>

      <nav className="flex flex-col gap-1">
        {NAV_ITEMS.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium",
                active
                  ? "bg-primary-subtle text-primary"
                  : "text-muted hover:bg-muted-subtle hover:text-foreground"
              )}
            >
              <span aria-hidden>{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="mt-auto rounded-xl bg-muted-subtle px-3 py-3 text-xs text-muted">
        Version 1.0 · Kerne-moduler
      </div>
    </aside>
  );
}
