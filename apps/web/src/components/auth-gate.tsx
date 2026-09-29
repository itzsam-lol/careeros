"use client";

import { Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAuth } from "@/lib/auth";

/** Renders children only for signed-in users; otherwise shows the sign-in screen. */
export function AuthGate({ children }: { children: React.ReactNode }) {
  const { status, signIn } = useAuth();

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
      <div className="flex min-h-screen items-center justify-center p-6">
        <div className="flex max-w-sm flex-col items-center gap-5 text-center">
          <span className="flex size-12 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            <Sparkles className="size-6" aria-hidden />
          </span>
          <div className="space-y-1.5">
            <h1 className="text-2xl font-semibold tracking-tight">Welcome to CareerOS</h1>
            <p className="text-sm text-muted-foreground">
              Your personal career agent. Sign in to see your opportunities.
            </p>
          </div>
          <Button size="lg" onClick={() => void signIn()}>
            Continue with Google
          </Button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
