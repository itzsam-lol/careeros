"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { type Schema, unwrap, useApi } from "@/lib/api";

export type JobCard = Schema<"JobCard">;
export type JobDetail = Schema<"JobDetail">;
export type JobView = Schema<"JobView">;
export type JobSort = Schema<"JobSort">;

export function useJobs(params: { view: JobView; sort: JobSort; q?: string; limit?: number; offset?: number }) {
  const api = useApi();
  return useQuery({
    queryKey: ["jobs", params],
    queryFn: () =>
      unwrap(
        api.GET("/api/v1/jobs", {
          params: {
            query: {
              view: params.view,
              sort: params.sort,
              q: params.q || undefined,
              limit: params.limit ?? 30,
              offset: params.offset ?? 0,
            },
          },
        }),
      ),
    placeholderData: (previous) => previous,
  });
}

export function useJob(jobId: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["job", jobId],
    queryFn: () => unwrap(api.GET("/api/v1/jobs/{job_id}", { params: { path: { job_id: jobId } } })),
  });
}

export function useJobActions(jobId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  const onSuccess = (detail: JobDetail) => {
    queryClient.setQueryData(["job", jobId], detail);
    void queryClient.invalidateQueries({ queryKey: ["jobs"] });
    void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
  const path = { params: { path: { job_id: jobId } } };
  return {
    save: useMutation({
      mutationFn: () => unwrap(api.POST("/api/v1/jobs/{job_id}/save", path)),
      onSuccess: (d) => {
        onSuccess(d);
        toast.success("Saved to your shortlist");
      },
    }),
    dismiss: useMutation({
      mutationFn: (reason?: string) =>
        unwrap(api.POST("/api/v1/jobs/{job_id}/dismiss", { ...path, body: { reason: reason ?? null } })),
      onSuccess: (d) => {
        onSuccess(d);
        toast("Dismissed", { description: "It won't show up in your inbox anymore." });
      },
    }),
    restore: useMutation({
      mutationFn: () => unwrap(api.POST("/api/v1/jobs/{job_id}/restore", path)),
      onSuccess,
    }),
    rematch: useMutation({
      mutationFn: () => unwrap(api.POST("/api/v1/jobs/{job_id}/rematch", path)),
      onSuccess: () => {
        toast.success("Re-matching queued", { description: "The score refreshes in a few seconds." });
        setTimeout(() => void queryClient.invalidateQueries({ queryKey: ["job", jobId] }), 4000);
      },
    }),
  };
}

export function scoreTone(score: number, eligible: boolean): "strong" | "good" | "partial" | "weak" | "ineligible" {
  if (!eligible) return "ineligible";
  if (score >= 0.75) return "strong";
  if (score >= 0.55) return "good";
  if (score >= 0.4) return "partial";
  return "weak";
}
