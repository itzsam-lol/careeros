import { storage } from "@/lib/storage";

/**
 * Where the signed-in session is kept. Shared by the auth provider and by background work
 * (alerts), which runs without React and reads the session straight from the keystore.
 */
export const SERVER_KEY = "careeros.server";
export const SESSION_KEY = "careeros.session";
export const DEFAULT_SERVER = (process.env.EXPO_PUBLIC_API_BASE_URL ?? "").replace(/\/$/, "");

export interface Session {
  token: string;
  email: string;
  name: string | null;
  expiresAt: number;
}

/** The server and token of the stored session, or null when signed out or expired. */
export async function storedCredentials(): Promise<{ server: string; token: string } | null> {
  const [server, raw] = await Promise.all([storage.get(SERVER_KEY), storage.get(SESSION_KEY)]);
  if (!raw) return null;
  try {
    const session = JSON.parse(raw) as Session;
    if (session.expiresAt * 1000 <= Date.now()) return null;
    return { server: (server || DEFAULT_SERVER).replace(/\/$/, ""), token: session.token };
  } catch {
    return null;
  }
}
