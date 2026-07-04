"use client";

import { useState, type FormEvent } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/Button";
import { Callout } from "@/components/ui/Callout";
import { Input, Label } from "@/components/ui/Input";
import { createClient } from "@/lib/supabase/client";

export function SignupForm() {
  const router = useRouter();
  const [companyName, setCompanyName] = useState("");
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fejl, setFejl] = useState<string | null>(null);
  const [bekraeftBesked, setBekraeftBesked] = useState<string | null>(null);
  const [indlaeser, setIndlaeser] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setFejl(null);
    setBekraeftBesked(null);
    setIndlaeser(true);

    const supabase = createClient();
    const { data, error } = await supabase.auth.signUp({
      email,
      password,
      options: {
        data: { company_name: companyName, full_name: fullName },
      },
    });

    setIndlaeser(false);

    if (error) {
      setFejl(error.message);
      return;
    }

    if (data.session) {
      router.push("/dashboard");
      router.refresh();
      return;
    }

    // Email-bekræftelse er slået til i Supabase-projektet — ingen session endnu.
    setBekraeftBesked("Tjek din e-mail og bekræft kontoen for at logge ind.");
  }

  if (bekraeftBesked) {
    return <Callout tone="success">{bekraeftBesked}</Callout>;
  }

  return (
    <form onSubmit={handleSubmit} className="flex flex-col gap-4">
      {fejl && <Callout tone="danger">{fejl}</Callout>}

      <div>
        <Label htmlFor="company">Virksomhedsnavn</Label>
        <Input id="company" required value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
      </div>

      <div>
        <Label htmlFor="fullName">Dit navn</Label>
        <Input id="fullName" required value={fullName} onChange={(e) => setFullName(e.target.value)} />
      </div>

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
          autoComplete="new-password"
          required
          minLength={6}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
      </div>

      <Button type="submit" size="lg" disabled={indlaeser} className="mt-2 w-full">
        {indlaeser ? "Opretter konto..." : "Opret konto"}
      </Button>
    </form>
  );
}
