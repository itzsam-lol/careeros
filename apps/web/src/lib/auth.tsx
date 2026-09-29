"use client";

import { toApiError } from "@careeros/api-client";
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { env } from "@/lib/env";

type AuthStatus = "loading" | "signed-in" | "signed-out";

interface AuthUser {
  email: string | null;
  name: string | null;
}

interface AuthContextValue {
  status: AuthStatus;
  user: AuthUser | null;
  mode: "dev" | "password" | "firebase";
  getToken: () => Promise<string | null>;
  /** Password mode takes credentials; Firebase mode opens Google sign-in. */
  signIn: (email?: string, password?: string) => Promise<void>;
  signOut: () => Promise<void>;
  /** Replace the stored session (after a password change the server issues a new token). */
  setSession?: (session: StoredSession) => void;
}

export interface StoredSession {
  token: string;
  email: string;
  name: string | null;
  expiresAt: number;
}

const AuthContext = createContext<AuthContextValue | null>(null);
const SESSION_KEY = "careeros.session";

function readSession(): StoredSession | null {
  try {
    const raw = window.localStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as StoredSession;
    if (!session.token || session.expiresAt * 1000 < Date.now()) return null;
    return session;
  } catch {
    return null;
  }
}

function DevAuthProvider({ children }: { children: React.ReactNode }) {
  const value = useMemo<AuthContextValue>(
    () => ({
      status: "signed-in",
      user: { email: "dev@careeros.local", name: "Developer" },
      mode: "dev",
      getToken: async () => env.devAuthToken,
      signIn: async () => undefined,
      signOut: async () => undefined,
    }),
    [],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function PasswordAuthProvider({ children }: { children: React.ReactNode }) {
  const [session, setSessionState] = useState<StoredSession | null>(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    // Hydrate from storage after mount (localStorage is unavailable during prerendering).
    const stored = readSession();
    queueMicrotask(() => {
      setSessionState(stored);
      setLoaded(true);
    });
  }, []);

  const setSession = useCallback((next: StoredSession | null) => {
    setSessionState(next);
    try {
      if (next) window.localStorage.setItem(SESSION_KEY, JSON.stringify(next));
      else window.localStorage.removeItem(SESSION_KEY);
    } catch {
      // Private mode or blocked storage: the session simply lasts for this tab.
    }
  }, []);

  const signIn = useCallback(
    async (email?: string, password?: string) => {
      const response = await fetch(`${env.apiBaseUrl.replace(/\/$/, "")}/api/v1/auth/login`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      const body: unknown = await response.json().catch(() => null);
      if (!response.ok) throw toApiError(response.status, body);
      const data = body as { access_token: string; email: string; name: string | null; expires_at: number };
      setSession({ token: data.access_token, email: data.email, name: data.name, expiresAt: data.expires_at });
    },
    [setSession],
  );

  const signOut = useCallback(async () => setSession(null), [setSession]);
  const getToken = useCallback(async () => readSession()?.token ?? null, []);

  const value = useMemo<AuthContextValue>(
    () => ({
      status: !loaded ? "loading" : session ? "signed-in" : "signed-out",
      user: session ? { email: session.email, name: session.name } : null,
      mode: "password",
      getToken,
      signIn,
      signOut,
      setSession,
    }),
    [loaded, session, getToken, signIn, signOut, setSession],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

function FirebaseAuthProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    let unsubscribe: (() => void) | undefined;
    void import("@/lib/firebase").then(({ firebaseAuth, onIdTokenChanged }) => {
      unsubscribe = onIdTokenChanged(firebaseAuth(), (fbUser) => {
        setUser(fbUser ? { email: fbUser.email, name: fbUser.displayName } : null);
        setStatus(fbUser ? "signed-in" : "signed-out");
      });
    });
    return () => unsubscribe?.();
  }, []);

  const getToken = useCallback(async () => {
    const { firebaseAuth } = await import("@/lib/firebase");
    // getIdToken() transparently refreshes tokens that are about to expire.
    return (await firebaseAuth().currentUser?.getIdToken()) ?? null;
  }, []);

  const signIn = useCallback(async () => {
    const { firebaseAuth, GoogleAuthProvider, signInWithPopup } = await import("@/lib/firebase");
    await signInWithPopup(firebaseAuth(), new GoogleAuthProvider());
  }, []);

  const signOut = useCallback(async () => {
    const { firebaseAuth, signOut: fbSignOut } = await import("@/lib/firebase");
    await fbSignOut(firebaseAuth());
  }, []);

  const value = useMemo<AuthContextValue>(
    () => ({ status, user, mode: "firebase", getToken, signIn, signOut }),
    [status, user, getToken, signIn, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  if (env.authMode === "firebase") return <FirebaseAuthProvider>{children}</FirebaseAuthProvider>;
  if (env.authMode === "password") return <PasswordAuthProvider>{children}</PasswordAuthProvider>;
  return <DevAuthProvider>{children}</DevAuthProvider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
