import { type ApiClient, createApiClient, type Schema, unwrap } from "@careeros/api-client";
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import * as WebBrowser from "expo-web-browser";
import { useMemo } from "react";
import { Linking } from "react-native";

import { useAuth } from "@/lib/auth";
import { usePrefs } from "@/lib/prefs";

export { ApiError } from "@careeros/api-client";
export type { Schema };
export type JobCard = Schema<"JobCard">;
export type JobDetail = Schema<"JobDetail">;
export type JobView = Schema<"JobView">;
export type JobSort = Schema<"JobSort">;
export type Notification = Schema<"NotificationOut">;
export type UserSettings = Schema<"UserSettings">;
export type Preferences = Schema<"PreferencesOut">;

export function useApi(): ApiClient {
  const { server, getToken, signOut } = useAuth();
  return useMemo(
    () => createApiClient({ baseUrl: server, getToken, onUnauthorized: () => void signOut() }),
    [server, getToken, signOut],
  );
}

/** Background polling interval chosen in Settings (false = only on demand). */
function usePolling(): number | false {
  const { prefs } = usePrefs();
  return prefs.refreshMinutes > 0 ? prefs.refreshMinutes * 60_000 : false;
}

/** Opens a link in the in-app browser or the system browser, per the user's preference. */
export function useOpenLink() {
  const { prefs } = usePrefs();
  return (url: string) => {
    if (prefs.openLinks === "browser") void Linking.openURL(url);
    else void WebBrowser.openBrowserAsync(url);
  };
}

export function useMe() {
  const api = useApi();
  return useQuery({ queryKey: ["me"], queryFn: () => unwrap(api.GET("/api/v1/me")), staleTime: 5 * 60_000 });
}

export function useDashboard() {
  const api = useApi();
  return useQuery({
    queryKey: ["dashboard"],
    queryFn: () => unwrap(api.GET("/api/v1/dashboard")),
    refetchInterval: usePolling(),
  });
}

const PAGE = 20;

export function useJobs(view: JobView, q: string, sort: JobSort) {
  const api = useApi();
  const effectiveSort: JobSort = view === "DEADLINE_SOON" ? "DEADLINE" : sort;
  return useInfiniteQuery({
    queryKey: ["jobs", view, q, effectiveSort],
    initialPageParam: 0,
    queryFn: ({ pageParam }) =>
      unwrap(
        api.GET("/api/v1/jobs", {
          params: { query: { view, sort: effectiveSort, q: q || undefined, limit: PAGE, offset: pageParam } },
        }),
      ),
    getNextPageParam: (last, pages) => {
      const loaded = pages.reduce((n, page) => n + page.items.length, 0);
      return loaded < last.total ? loaded : undefined;
    },
  });
}

export function useJob(jobId: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => unwrap(api.GET("/api/v1/jobs/{job_id}", { params: { path: { job_id: jobId } } })),
  });
}

export function useJobAction(jobId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async (action: "save" | "dismiss" | "restore") => {
      const path = { params: { path: { job_id: jobId } } };
      if (action === "save") return unwrap(api.POST("/api/v1/jobs/{job_id}/save", path));
      if (action === "dismiss") return unwrap(api.POST("/api/v1/jobs/{job_id}/dismiss", { ...path, body: { reason: null } }));
      return unwrap(api.POST("/api/v1/jobs/{job_id}/restore", path));
    },
    onSuccess: (detail) => {
      queryClient.setQueryData(["job", jobId], detail);
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useRematch(jobId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/jobs/{job_id}/rematch", { params: { path: { job_id: jobId } } })),
    // Matching runs on the worker; refresh once it has had time to finish.
    onSuccess: () => setTimeout(() => void queryClient.invalidateQueries({ queryKey: ["job", jobId] }), 4000),
  });
}

export function useNotifications() {
  const api = useApi();
  return useQuery({
    queryKey: ["notifications"],
    queryFn: () => unwrap(api.GET("/api/v1/notifications", { params: { query: { limit: 60 } } })),
    refetchInterval: usePolling(),
  });
}

export function useUnreadCount() {
  const api = useApi();
  return useQuery({
    queryKey: ["notifications", "unread"],
    queryFn: () => unwrap(api.GET("/api/v1/notifications/unread-count")),
    refetchInterval: usePolling(),
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

export function useProfile() {
  const api = useApi();
  return useQuery({ queryKey: ["profile"], queryFn: () => unwrap(api.GET("/api/v1/profile")) });
}

export function useVerify() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { section: string; ids: string[]; status: "VERIFIED" | "REJECTED" }) =>
      unwrap(api.POST("/api/v1/profile/verification", { body: input })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

/** Partial update of the job-search preferences (only the provided fields change). */
export function useUpdatePreferences() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: Schema<"PreferencesIn">) => unwrap(api.PUT("/api/v1/profile/preferences", { body: patch })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["profile"] });
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

export function useServerSettings() {
  const api = useApi();
  return useQuery({ queryKey: ["settings"], queryFn: () => unwrap(api.GET("/api/v1/me/settings")) });
}

/** Deep-merged PATCH of the server-side agent settings, applied optimistically. */
export function useUpdateServerSettings() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: Record<string, unknown>) => unwrap(api.PATCH("/api/v1/me/settings", { body: patch })),
    onMutate: async (patch) => {
      await queryClient.cancelQueries({ queryKey: ["settings"] });
      const previous = queryClient.getQueryData<UserSettings>(["settings"]);
      if (previous) {
        const next = { ...previous } as Record<string, unknown>;
        for (const [key, value] of Object.entries(patch)) {
          next[key] =
            value && typeof value === "object" && !Array.isArray(value)
              ? { ...((previous as Record<string, unknown>)[key] as object), ...value }
              : value;
        }
        queryClient.setQueryData(["settings"], next);
      }
      return { previous };
    },
    onError: (_error, _patch, context) => {
      if (context?.previous) queryClient.setQueryData(["settings"], context.previous);
    },
    onSuccess: (settings) => {
      queryClient.setQueryData(["settings"], settings);
      void queryClient.invalidateQueries({ queryKey: ["me"] });
    },
  });
}

export function useSources() {
  const api = useApi();
  return useQuery({ queryKey: ["sources"], queryFn: () => unwrap(api.GET("/api/v1/sources")), refetchInterval: 30_000 });
}

export function useSourceActions() {
  const api = useApi();
  const queryClient = useQueryClient();
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["sources"] });
  return {
    run: useMutation({
      mutationFn: (id: string) => unwrap(api.POST("/api/v1/sources/{source_id}/run", { params: { path: { source_id: id } } })),
      onSuccess: () => setTimeout(() => void refresh(), 4000),
    }),
    update: useMutation({
      mutationFn: (input: { id: string; patch: Schema<"SourceUpdate"> }) =>
        unwrap(api.PATCH("/api/v1/sources/{source_id}", { params: { path: { source_id: input.id } }, body: input.patch })),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: string) => {
        const { response } = await api.DELETE("/api/v1/sources/{source_id}", { params: { path: { source_id: id } } });
        if (!response.ok) throw new Error(`Could not delete the source (${response.status})`);
      },
      onSuccess: refresh,
    }),
    create: useMutation({
      mutationFn: (input: Schema<"SourceIn">) => unwrap(api.POST("/api/v1/sources", { body: input })),
      onSuccess: refresh,
    }),
  };
}

export function useLogoutEverywhere() {
  const api = useApi();
  const { signOut } = useAuth();
  return useMutation({
    mutationFn: async () => {
      const { response } = await api.POST("/api/v1/auth/logout-all");
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
    },
    onSuccess: () => void signOut(),
  });
}
