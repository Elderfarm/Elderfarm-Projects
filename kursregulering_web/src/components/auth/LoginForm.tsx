"use client";

import { useState, type FormEvent } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Input, Label } from "@/components/ui/Input";
import { createClient } from "@/lib/supabase/client";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fejl, setFejl] = useState<string | null>(null);
  const [indlaeser, setIndlaeser] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFejl(null);
    setIndlaeser(true);

    const supabase = createClient();
    const { error } = await supabase.auth.signInWithPassword({ email, password });

    setIndlaeser(false);

    if (error) {
      setFejl(
        error.message === "Invalid login credentials"
          ? "Forkert e-mail eller adgangskode."
          : error.message
      );
      return;
    }

    const naeste = searchParams.get("naeste") ?? "/dashboard";
    router.push(naeste);
    router.refresh();
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {fejl && <Callout tone="danger">{fejl}</Callout>}

      <div>
        <Label htmlFor="email">E-mail</Label>
        <Input
          id="email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
      </div>

      <div>
        <Label htmlFor="password">Adgangskode</Label>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>

      <Button type="submit" size="lg" disabled={indlaeser} className="mt-2 w-full">
        {indlaeser ? "Logger ind..." : "Log ind"}
      </Button>
    </form>
  );
}
