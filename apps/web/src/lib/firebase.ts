import { getApps, initializeApp } from "firebase/app";
import { getAuth, type Auth } from "firebase/auth";

import { env } from "@/lib/env";

export { GoogleAuthProvider, onIdTokenChanged, signInWithPopup, signOut } from "firebase/auth";

let auth: Auth | null = null;

/** Lazily initialised so the Firebase SDK is only loaded when AUTH_MODE=firebase. */
export function firebaseAuth(): Auth {
  if (!auth) {
    const app = getApps()[0] ?? initializeApp(env.firebase);
    auth = getAuth(app);
  }
  return auth;
}
