"use client";

import { Sparkles } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Field, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";

function PasswordSignIn() {
  const { signIn } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setPending(true);
    setError(null);
    try {
      await signIn(email.trim(), password);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not sign in");
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={submit} className="glass-strong w-full space-y-4 rounded-2xl p-6 text-left">
      <Field>
        <FieldLabel htmlFor="email">Email</FieldLabel>
        <Input id="email" type="email" autoComplete="username" value={email} onChange={(e) => setEmail(e.target.value)} required />
      </Field>
      <Field>
        <FieldLabel htmlFor="password">Password</FieldLabel>
        <Input
          id="password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
        />
      </Field>
      {error ? (
        <p role="alert" className="text-sm text-destructive">
          {error}
        </p>
      ) : null}
      <Button type="submit" className="w-full" size="lg" disabled={pending}>
        {pending ? "Signing in…" : "Sign in"}
      </Button>
    </form>
  );
}

/** Renders children only for signed-in users; otherwise shows the sign-in screen. */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { status, signIn, mode } = useAuth();

  if (status === "loading") {
    return (
      <div className="mx-auto flex max-w-md flex-col gap-3 p-10">
        <Skeleton className="h-8 w-40" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }

  if (status === "signed-out") {
    return (
      <div className="relative flex min-h-screen items-center justify-center p-6">
        <div aria-hidden className="app-backdrop fixed inset-0 -z-10" />
        <div className="flex w-full max-w-sm flex-col items-center gap-6 text-center">
          <span className="flex size-12 items-center justify-center rounded-2xl bg-gradient-to-br from-primary to-[oklch(0.62_0.17_300)] text-primary-foreground shadow-lg shadow-primary/30">
            <Sparkles className="size-6" aria-hidden />
          </span>
          <div className="space-y-1.5">
            <h1 className="text-2xl font-semibold tracking-tight">Welcome to CareerOS</h1>
            <p className="text-sm text-muted-foreground">Your personal career agent. Sign in to see your opportunities.</p>
          </div>
          {mode === "password" ? (
            <PasswordSignIn />
          ) : (
            <Button size="lg" onClick={() => void signIn()}>
              Continue with Google
            </Button>
          )}
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
