"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { unwrap, useApi } from "@/lib/api";

export function useUnreadCount() {
  const api = useApi();
  return useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => unwrap(api.GET("/api/v1/notifications/unread-count")),
    refetchInterval: 60_000,
  });
}

export function useNotifications(enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: ["notifications", "list"],
    queryFn: () => unwrap(api.GET("/api/v1/notifications", { params: { query: { limit: 30 } } })),
    enabled,
  });
}

export function useMarkRead() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (ids?: string[]) => unwrap(api.POST("/api/v1/notifications/read", { body: { ids: ids ?? null } })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["notifications"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}
