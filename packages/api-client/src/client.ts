import createClient, { type Middleware } from "openapi-fetch";

import type { paths } from "./schema";

export interface ApiClientOptions {
  baseUrl: string;
  /** Returns the current bearer token (Firebase ID token, or the dev token locally). */
  getToken: () => Promise<string | null> | string | null;
  /** Called when the API rejects the token, e.g. to sign the user out. */
  onUnauthorized?: () => void;
  fetch?: typeof globalThis.fetch;
}

/** Error envelope returned by the API: {"error": {"code", "message", "details"}}. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

export function toApiError(status: number, body: unknown): ApiError {
  if (body && typeof body === "object" && "error" in body) {
    const envelope = (body as { error?: { code?: string; message?: string; details?: Record<string, unknown> } })
      .error;
    if (envelope) {
      return new ApiError(
        status,
        envelope.code ?? "http_error",
        envelope.message ?? `Request failed (${status})`,
        envelope.details ?? {},
      );
    }
  }
  return new ApiError(status, "http_error", `Request failed (${status})`);
}

export function createApiClient(options: ApiClientOptions) {
  const client = createClient<paths>({
    baseUrl: options.baseUrl.replace(/\/$/, ""),
    fetch: options.fetch,
  });

  // Middleware returns nothing when it does not replace the request/response: openapi-fetch
  // checks returned values with `instanceof Request/Response`, which fails for the fetch
  // polyfill classes on React Native even when the object is passed straight back.
  const auth: Middleware = {
    async onRequest({ request }) {
      const token = await options.getToken();
      if (token) request.headers.set("Authorization", `Bearer ${token}`);
    },
    onResponse({ response }) {
      if (response.status === 401) options.onUnauthorized?.();
    },
  };
  client.use(auth);
  return client;
}

export type ApiClient = ReturnType<typeof createApiClient>;

type FetchResult<T> = { data?: T; error?: unknown; response: Response };

/** Resolve an openapi-fetch call to its data, throwing `ApiError` on failure. */
export async function unwrap<T>(call: Promise<FetchResult<T>>): Promise<T> {
  const { data, error, response } = await call;
  if (!response.ok || error !== undefined) {
    throw toApiError(response.status, error);
  }
  return data as T;
}
