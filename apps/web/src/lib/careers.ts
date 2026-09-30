"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";

import { type Schema, unwrap, useApi } from "@/lib/api";

export type DocumentSummary = Schema<"DocumentSummary">;
export type DocumentDetail = Schema<"DocumentDetail">;
export type ApplicationStage = Schema<"ApplicationStage">;

export const STAGES: { value: ApplicationStage; label: string }[] = [
  { value: "PLANNED", label: "Planned" },
  { value: "APPLIED", label: "Applied" },
  { value: "ASSESSMENT", label: "Assessment" },
  { value: "INTERVIEW", label: "Interview" },
  { value: "OFFER", label: "Offer" },
  { value: "ACCEPTED", label: "Accepted" },
  { value: "REJECTED", label: "Rejected" },
  { value: "WITHDRAWN", label: "Withdrawn" },
];

export function coverageText(doc: Pick<DocumentSummary, "coverage_before" | "coverage_after">): string | null {
  if (doc.coverage_after == null) return null;
  const after = Math.round(doc.coverage_after * 100);
  const before = doc.coverage_before == null ? null : Math.round(doc.coverage_before * 100);
  return before == null || before === after ? `${after}% skill match` : `${before}% → ${after}% skill match`;
}

export function useMaster() {
  const api = useApi();
  return useQuery({
    queryKey: ["resume-master"],
    queryFn: () => unwrap(api.GET("/api/v1/resumes/master")),
    refetchInterval: (query) => {
      const master = query.state.data;
      return master && !master.has_pdf && !master.compile_error ? 3000 : false;
    },
  });
}

export function useUploadMaster() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { tex: string; filename: string }) => unwrap(api.PUT("/api/v1/resumes/master", { body: input })),
    onSuccess: (master) => {
      queryClient.setQueryData(["resume-master"], master);
      toast.success("Master résumé uploaded", { description: "Compiling it now; this takes a few seconds." });
    },
    onError: (error) => toast.error("Upload failed", { description: error.message }),
  });
}

export function useDocuments(jobId?: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["documents", jobId ?? "all"],
    queryFn: () => unwrap(api.GET("/api/v1/resumes", { params: { query: jobId ? { job_id: jobId } : {} } })),
    refetchInterval: (query) => (query.state.data?.some((d) => d.status === "PENDING") ? 3000 : false),
  });
}

export function useDocument(id: string | null) {
  const api = useApi();
  return useQuery({
    queryKey: ["document", id],
    enabled: !!id,
    queryFn: () => unwrap(api.GET("/api/v1/resumes/{document_id}", { params: { path: { document_id: id ?? "" } } })),
  });
}

export function useCreateDocument() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { jobId?: string | null; kind: "RESUME" | "COVER_LETTER"; tone?: "professional" | "warm" | "concise" }) =>
      unwrap(
        api.POST("/api/v1/resumes", {
          body: {
            job_id: input.jobId ?? null,
            kind: input.kind,
            options: { tone: input.tone ?? "professional", max_pages: 1, swap_projects: true, add_skills: true, rephrase: true, max_projects: null },
          },
        }),
      ),
    onSuccess: (doc) => {
      void queryClient.invalidateQueries({ queryKey: ["documents"] });
      toast.success(doc.kind === "COVER_LETTER" ? "Writing your cover letter" : "Tailoring your résumé", {
        description: "It will appear in Résumés in a few seconds.",
      });
    },
    onError: (error) => toast.error("Couldn't start", { description: error.message }),
  });
}

/** Open a document (or the master when id is null) in a new tab via a short-lived signed link. */
export function useOpenPdf() {
  const api = useApi();
  return useMutation({
    mutationFn: async (id: string | null) => {
      const link = id
        ? await unwrap(api.POST("/api/v1/resumes/{document_id}/link", { params: { path: { document_id: id } } }))
        : await unwrap(api.POST("/api/v1/resumes/master/link"));
      window.open(link.url, "_blank", "noopener,noreferrer");
    },
    onError: (error) => toast.error("Couldn't open the PDF", { description: error.message }),
  });
}

export function useDocumentActions() {
  const api = useApi();
  const queryClient = useQueryClient();
  const refresh = () => void queryClient.invalidateQueries({ queryKey: ["documents"] });
  return {
    star: useMutation({
      mutationFn: (input: { id: string; starred: boolean }) =>
        unwrap(api.PATCH("/api/v1/resumes/{document_id}", { params: { path: { document_id: input.id } }, body: { starred: input.starred } })),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async (id: string) => {
        const { response } = await api.DELETE("/api/v1/resumes/{document_id}", { params: { path: { document_id: id } } });
        if (!response.ok) throw new Error(`Delete failed (${response.status})`);
      },
      onSuccess: refresh,
    }),
  };
}

export function useUpdateApplication(jobId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<Schema<"ApplicationUpdate">>) =>
      unwrap(api.PATCH("/api/v1/jobs/{job_id}/application", { params: { path: { job_id: jobId } }, body: { clear_follow_up: false, ...patch } })),
    onSuccess: (application) => {
      queryClient.setQueryData(["application", jobId], application);
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
    onError: (error) => toast.error("Couldn't update the application", { description: error.message }),
  });
}

export function useApplication(jobId: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["application", jobId],
    queryFn: () => unwrap(api.GET("/api/v1/jobs/{job_id}/application", { params: { path: { job_id: jobId } } })),
  });
}
