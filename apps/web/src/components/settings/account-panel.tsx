"use client";

import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { unwrap, useApi } from "@/lib/api";
import { useAuth } from "@/lib/auth";

export function AccountPanel() {
  const api = useApi();
  const { mode, user, signOut, setSession } = useAuth();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");

  const change = useMutation({
    mutationFn: () =>
      unwrap(api.POST("/api/v1/auth/change-password", { body: { current_password: current, new_password: next } })),
    onSuccess: (session) => {
      setSession?.({ token: session.access_token, email: session.email, name: session.name ?? null, expiresAt: session.expires_at });
      setCurrent("");
      setNext("");
      toast.success("Password changed", { description: "Other devices have been signed out." });
    },
    onError: (error) => toast.error(error.message),
  });

  const everywhere = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/auth/logout-all")),
    onSuccess: () => void signOut(),
    onError: (error) => toast.error(error.message),
  });

  if (mode !== "password") {
    return (
      <section className="space-y-2">
        <h2 className="text-lg font-semibold">Account</h2>
        <p className="glass rounded-2xl p-4 text-sm text-muted-foreground">
          Signed in as {user?.email ?? "developer"} ({mode === "dev" ? "local development" : "Google"}).
        </p>
      </section>
    );
  }

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Account</h2>
        <p className="text-sm text-muted-foreground">Signed in as {user?.email}.</p>
      </div>
      <form
        className="glass grid gap-4 rounded-2xl p-5 md:grid-cols-2"
        onSubmit={(event) => {
          event.preventDefault();
          change.mutate();
        }}
      >
        <Field>
          <FieldLabel htmlFor="current-password">Current password</FieldLabel>
          <Input id="current-password" type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} required />
        </Field>
        <Field>
          <FieldLabel htmlFor="new-password">New password</FieldLabel>
          <Input id="new-password" type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} minLength={10} required />
          <FieldDescription>At least 10 characters with upper- and lower-case letters and a digit.</FieldDescription>
        </Field>
        <div className="flex flex-wrap justify-between gap-2 md:col-span-2">
          <Button type="button" variant="outline" onClick={() => everywhere.mutate()} disabled={everywhere.isPending}>
            Sign out on all devices
          </Button>
          <Button type="submit" disabled={change.isPending || !current || next.length < 10}>
            {change.isPending ? "Saving…" : "Change password"}
          </Button>
        </div>
      </form>
    </section>
  );
}
