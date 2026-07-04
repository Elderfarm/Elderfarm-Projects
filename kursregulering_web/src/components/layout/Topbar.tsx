"use client";

import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { createClient } from "@/lib/supabase/client";

interface TopbarProps {
  email: string | null;
  companyName: string | null;
}

export function Topbar({ email, companyName }: TopbarProps) {
  const router = useRouter();

  async function logUd() {
    const supabase = createClient();
    await supabase.auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="flex h-16 items-center justify-between border-b border-border bg-surface px-6">
      <div>
        <p className="text-sm font-medium text-foreground">{companyName ?? "Din virksomhed"}</p>
        <p className="text-xs text-muted">{email}</p>
      </div>
      <Button variant="ghost" size="sm" onClick={logUd}>
        Log ud
      </Button>
    </header>
  );
}
