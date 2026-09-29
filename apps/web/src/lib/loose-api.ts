import type { ApiClient } from "@careeros/api-client";

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
type Result = { data?: unknown; error?: unknown; response: Response };
type LooseCall = (path: string, init?: { body?: unknown }) => Promise<Result>;

/**
 * Escape hatch for generic screens (e.g. profile sections) that address several typed endpoints
 * through one code path. Auth, base URL and error handling are still those of the typed client.
 */
export function looseCall(api: ApiClient, method: Method, path: string, body?: unknown): Promise<Result> {
  const call = (api as unknown as Record<Method, LooseCall>)[method];
  return call(path, body === undefined ? undefined : { body });
}
