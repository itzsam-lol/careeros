import { toApiError } from "@careeros/api-client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { storage } from "@/lib/storage";

/**
 * On devices the session lives in the OS keystore (expo-secure-store), never in plain storage.
 * The server URL is configurable so one APK works with any CareerOS deployment.
 */
const SERVER_KEY = "careeros.server";
const SESSION_KEY = "careeros.session";
export const DEFAULT_SERVER = (process.env.EXPO_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

export interface Session {
  token: string;
  email: string;
  name: string | null;
  expiresAt: number;
}

type Status = "loading" | "signed-in" | "signed-out";

interface AuthValue {
  status: Status;
  server: string;
  session: Session | null;
  signIn: (server: string, email: string, password: string) => Promise<void>;
  signInDev: (server: string) => Promise<void>;
  signOut: () => Promise<void>;
  getToken: () => Promise<string | null>;
}

const AuthContext = createContext<AuthValue | null>(null);

export function normalizeServer(value: string): string {
  const trimmed = value.trim().replace(/\/$/, "");
  if (!trimmed) return trimmed;
  return /^https?:\/\//.test(trimmed) ? trimmed : `https://${trimmed}`;
}

export async function probeServer(server: string): Promise<{ mode: string; app_name: string }> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 10_000);
  try {
    const response = await fetch(`${server}/api/v1/auth/config`, { signal: controller.signal });
    if (!response.ok) throw new Error(`Server responded with ${response.status}`);
    return (await response.json()) as { mode: string; app_name: string };
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw new Error("The server did not respond in time");
    throw error instanceof Error ? error : new Error("Could not reach the server");
  } finally {
    clearTimeout(timer);
  }
}

export function AuthProvider({ children, onSignOut }: { children: React.ReactNode; onSignOut?: () => void }) {
  const [status, setStatus] = useState<Status>("loading");
  const [server, setServer] = useState(DEFAULT_SERVER);
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    void (async () => {
      const [storedServer, storedSession] = await Promise.all([
        storage.get(SERVER_KEY),
        storage.get(SESSION_KEY),
      ]);
      if (storedServer) setServer(storedServer);
      if (storedSession) {
        try {
          const parsed = JSON.parse(storedSession) as Session;
          if (parsed.expiresAt * 1000 > Date.now()) {
            setSession(parsed);
            setStatus("signed-in");
            return;
          }
        } catch {
          // fall through: corrupted value means signed out
        }
      }
      setStatus("signed-out");
    })();
  }, []);

  const persist = useCallback(async (nextServer: string, next: Session) => {
    await storage.set(SERVER_KEY, nextServer);
    await storage.set(SESSION_KEY, JSON.stringify(next));
    setServer(nextServer);
    setSession(next);
    setStatus("signed-in");
  }, []);

  const signIn = useCallback(
    async (rawServer: string, email: string, password: string) => {
      const nextServer = normalizeServer(rawServer);
      const response = await fetch(`${nextServer}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: email.trim(), password }),
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) throw toApiError(response.status, body);
      const data = body as { access_token: string; email: string; name: string | null; expires_at: number };
      await persist(nextServer, { token: data.access_token, email: data.email, name: data.name, expiresAt: data.expires_at });
    },
    [persist],
  );

  const signInDev = useCallback(
    async (rawServer: string) => {
      const nextServer = normalizeServer(rawServer);
      const token = "dev-token";
      const me = await fetch(`${nextServer}/api/v1/me`, { headers: { Authorization: `Bearer ${token}` } });
      if (!me.ok) throw new Error("This server does not accept development sign-in");
      const body = (await me.json()) as { email: string; name: string | null };
      await persist(nextServer, { token, email: body.email, name: body.name, expiresAt: Date.now() / 1000 + 86_400 * 365 });
    },
    [persist],
  );

  const signOut = useCallback(async () => {
    await storage.remove(SESSION_KEY);
    setSession(null);
    setStatus("signed-out");
    onSignOut?.();
  }, [onSignOut]);

  const getToken = useCallback(async () => session?.token ?? null, [session]);

  const value = useMemo<AuthValue>(
    () => ({ status, server, session, signIn, signInDev, signOut, getToken }),
    [status, server, session, signIn, signInDev, signOut, getToken],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
