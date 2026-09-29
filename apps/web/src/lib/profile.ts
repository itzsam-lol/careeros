"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback } from "react";

import { unwrap, useApi } from "@/lib/api";

export const PROFILE_KEY = ["profile"] as const;

export function useProfile() {
  const api = useApi();
  return useQuery({
    queryKey: PROFILE_KEY,
    queryFn: () => unwrap(api.GET("/api/v1/profile")),
  });
}

export function useInvalidateProfile() {
  const queryClient = useQueryClient();
  return useCallback(() => queryClient.invalidateQueries({ queryKey: PROFILE_KEY }), [queryClient]);
}

/** Maps a FastAPI 422 envelope to {field: message}. */
export function fieldErrors(details: Record<string, unknown>): Record<string, string> {
  const errors = Array.isArray(details.errors) ? details.errors : [];
  const result: Record<string, string> = {};
  for (const error of errors as { loc?: unknown[]; msg?: string }[]) {
    const loc = error.loc ?? [];
    const field = loc.find((part, index) => index > 0 && typeof part === "string");
    if (typeof field === "string" && error.msg) result[field] = error.msg.replace(/^Value error, /, "");
  }
  return result;
}
