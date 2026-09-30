import { describe, expect, it, vi } from "vitest";

import { createApiClient, unwrap } from "./client";

/** A Response look-alike that is *not* `instanceof Response`, like the React Native fetch polyfill. */
class ForeignResponse {
  readonly headers: Headers;
  readonly ok: boolean;
  readonly redirected = false;
  readonly statusText = "";
  readonly type = "default";
  readonly url = "";
  readonly bodyUsed = false;
  readonly body = null;
  constructor(
    private readonly payload: unknown,
    readonly status = 200,
  ) {
    this.ok = status >= 200 && status < 300;
    this.headers = new Headers({ "Content-Type": "application/json" });
  }
  async json() {
    return this.payload;
  }
  async text() {
    return JSON.stringify(this.payload);
  }
  clone() {
    return new ForeignResponse(this.payload, this.status);
  }
}

describe("createApiClient", () => {
  it("works with non-standard Response classes and sends the bearer token", async () => {
    const seen: string[] = [];
    const fetchImpl = vi.fn(async (input: Request) => {
      seen.push(input.headers.get("Authorization") ?? "");
      return new ForeignResponse({ unread: 3 }) as unknown as Response;
    });
    const api = createApiClient({ baseUrl: "https://api.test/", getToken: () => "tok", fetch: fetchImpl as unknown as typeof fetch });
    const data = await unwrap(api.GET("/api/v1/notifications/unread-count"));
    expect(data).toEqual({ unread: 3 });
    expect(seen).toEqual(["Bearer tok"]);
  });

  it("reports 401 responses to onUnauthorized", async () => {
    const onUnauthorized = vi.fn();
    const fetchImpl = vi.fn(async () => new ForeignResponse({ error: { code: "unauthenticated", message: "no" } }, 401) as unknown as Response);
    const api = createApiClient({ baseUrl: "https://api.test", getToken: () => null, onUnauthorized, fetch: fetchImpl as unknown as typeof fetch });
    await expect(unwrap(api.GET("/api/v1/me"))).rejects.toMatchObject({ status: 401, code: "unauthenticated" });
    expect(onUnauthorized).toHaveBeenCalledOnce();
  });
});
