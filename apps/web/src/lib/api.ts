"use client";

import { createApiClient, type ApiClient } from "@careeros/api-client";
import { useMemo } from "react";

import { useAuth } from "@/lib/auth";
import { env } from "@/lib/env";

export { ApiError, unwrap } from "@careeros/api-client";
export type { Schema } from "@careeros/api-client";

/** The typed API client bound to the current user's token. */
export function useApi(): ApiClient {
  const { getToken, signOut, mode } = useAuth();
  return useMemo(
    () =>
      createApiClient({
        baseUrl: env.apiBaseUrl,
        getToken,
        onUnauthorized: mode === "firebase" ? () => void signOut() : undefined,
      }),
    [getToken, signOut, mode],
  );
}
