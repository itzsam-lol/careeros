"use client";

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
  mode: "dev" | "firebase";
  getToken: () => Promise<string | null>;
  signIn: () => Promise<void>;
  signOut: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

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
  return env.authMode === "firebase" ? (
    <FirebaseAuthProvider>{children}</FirebaseAuthProvider>
  ) : (
    <DevAuthProvider>{children}</DevAuthProvider>
  );
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
