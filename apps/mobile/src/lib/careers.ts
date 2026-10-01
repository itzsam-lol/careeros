import { type Schema, unwrap } from "@careeros/api-client";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useApi } from "@/lib/api";

export type DocumentSummary = Schema<"DocumentSummary">;
export type DocumentDetail = Schema<"DocumentDetail">;
export type DocumentKind = Schema<"DocumentKind">;
export type Master = Schema<"MasterOut">;
export type Application = Schema<"ApplicationOut">;
export type ApplicationStage = Schema<"ApplicationStage">;
export type CatalogBoard = Schema<"CatalogBoard">;
export type Draft = Schema<"Draft">;

export interface TalkingPoint {
  topic: string;
  status: "STRONG" | "RELATED" | "GAP";
  evidence: string[];
  tip: string;
}

export interface Prep {
  talking_points: TalkingPoint[];
  behavioural: { question: string; story: string; where: string }[];
  questions_to_ask: string[];
  summary: { strong: number; related: number; gaps: number };
}

export const STAGES: { value: ApplicationStage; label: string; tone: "neutral" | "accent" | "good" | "warn" | "bad" }[] = [
  { value: "PLANNED", label: "Planned", tone: "neutral" },
  { value: "APPLIED", label: "Applied", tone: "accent" },
  { value: "ASSESSMENT", label: "Assessment", tone: "warn" },
  { value: "INTERVIEW", label: "Interview", tone: "warn" },
  { value: "OFFER", label: "Offer", tone: "good" },
  { value: "ACCEPTED", label: "Accepted", tone: "good" },
  { value: "REJECTED", label: "Rejected", tone: "bad" },
  { value: "WITHDRAWN", label: "Withdrawn", tone: "neutral" },
];

export function coverageText(doc: Pick<DocumentSummary, "coverage_before" | "coverage_after">): string | null {
  if (doc.coverage_after == null) return null;
  const after = Math.round(doc.coverage_after * 100);
  const before = doc.coverage_before == null ? null : Math.round(doc.coverage_before * 100);
  return before == null || before === after ? `${after}% skill match` : `${before}% → ${after}% skill match`;
}

export function stageInfo(stage: ApplicationStage | null | undefined) {
  return STAGES.find((s) => s.value === stage);
}

// --- résumés & cover letters ---------------------------------------------------------------

export function useMaster() {
  const api = useApi();
  return useQuery({
    queryKey: ["resume-master"],
    queryFn: () => unwrap(api.GET("/api/v1/resumes/master")),
    // Compiling happens in the background right after an upload.
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
    onSuccess: (master) => queryClient.setQueryData(["resume-master"], master),
  });
}

export function useMasterLink() {
  const api = useApi();
  return useMutation({ mutationFn: () => unwrap(api.POST("/api/v1/resumes/master/link")) });
}

export function useDocuments(jobId?: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["documents", jobId ?? "all"],
    queryFn: () => unwrap(api.GET("/api/v1/resumes", { params: { query: jobId ? { job_id: jobId } : {} } })),
    refetchInterval: (query) => (query.state.data?.some((d) => d.status === "PENDING") ? 3000 : false),
  });
}

export function useDocument(id: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["document", id],
    queryFn: () => unwrap(api.GET("/api/v1/resumes/{document_id}", { params: { path: { document_id: id } } })),
    refetchInterval: (query) => (query.state.data?.status === "PENDING" ? 2500 : false),
  });
}

export function useCreateDocument() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { jobId?: string | null; kind: DocumentKind; tone?: "professional" | "warm" | "concise"; maxPages?: number; swapProjects?: boolean; addSkills?: boolean }) =>
      unwrap(
        api.POST("/api/v1/resumes", {
          body: {
            job_id: input.jobId ?? null,
            kind: input.kind,
            options: {
              tone: input.tone ?? "professional",
              max_pages: input.maxPages ?? 1,
              swap_projects: input.swapProjects ?? true,
              add_skills: input.addSkills ?? true,
              rephrase: true,
              max_projects: null,
            },
          },
        }),
      ),
    onSuccess: () => void queryClient.invalidateQueries({ queryKey: ["documents"] }),
  });
}

export function useDocumentActions(id: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  const refresh = () => {
    void queryClient.invalidateQueries({ queryKey: ["documents"] });
    void queryClient.invalidateQueries({ queryKey: ["document", id] });
  };
  return {
    star: useMutation({
      mutationFn: (starred: boolean) =>
        unwrap(api.PATCH("/api/v1/resumes/{document_id}", { params: { path: { document_id: id } }, body: { starred } })),
      onSuccess: refresh,
    }),
    remove: useMutation({
      mutationFn: async () => {
        const { response } = await api.DELETE("/api/v1/resumes/{document_id}", { params: { path: { document_id: id } } });
        if (!response.ok) throw new Error(`Could not delete (${response.status})`);
      },
      onSuccess: refresh,
    }),
    link: useMutation({
      mutationFn: () => unwrap(api.POST("/api/v1/resumes/{document_id}/link", { params: { path: { document_id: id } } })),
    }),
  };
}

// --- per-job coaching ------------------------------------------------------------------------

export function usePrep(jobId: string, enabled = true) {
  const api = useApi();
  return useQuery({
    queryKey: ["prep", jobId],
    enabled,
    queryFn: async () => (await unwrap(api.GET("/api/v1/jobs/{job_id}/prep", { params: { path: { job_id: jobId } } }))) as unknown as Prep,
  });
}

export function useOutreach(jobId: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["outreach", jobId],
    queryFn: () => unwrap(api.GET("/api/v1/jobs/{job_id}/outreach", { params: { path: { job_id: jobId } } })),
  });
}

// --- company insights ----------------------------------------------------------------------------

export type CompanyInsights = Schema<"CompanyInsightsOut">;

export function useCompany(jobId: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["company", jobId],
    queryFn: () => unwrap(api.GET("/api/v1/jobs/{job_id}/company", { params: { path: { job_id: jobId } } })),
    staleTime: 10 * 60_000,
  });
}

// --- application tracking ------------------------------------------------------------------------

export function useApplication(jobId: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["application", jobId],
    queryFn: () => unwrap(api.GET("/api/v1/jobs/{job_id}/application", { params: { path: { job_id: jobId } } })),
  });
}

export function useUpdateApplication(jobId: string) {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (patch: Partial<Schema<"ApplicationUpdate">>) =>
      unwrap(
        api.PATCH("/api/v1/jobs/{job_id}/application", {
          params: { path: { job_id: jobId } },
          body: { clear_follow_up: false, ...patch },
        }),
      ),
    onSuccess: (application) => {
      queryClient.setQueryData(["application", jobId], application);
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["job", jobId] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });
}

// --- board catalogue ---------------------------------------------------------------------------------

export function useCatalog(region: "IN" | "AU" | undefined, q: string) {
  const api = useApi();
  return useQuery({
    queryKey: ["catalog", region ?? "all", q],
    queryFn: () => unwrap(api.GET("/api/v1/sources/catalog", { params: { query: { region, q: q || undefined } } })),
  });
}

export function useAddFromCatalog() {
  const api = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: { ids?: string[]; all?: boolean; region?: "IN" | "AU" | null }) =>
      unwrap(api.POST("/api/v1/sources/catalog", { body: { ids: input.ids ?? [], all: input.all ?? false, region: input.region ?? null, cadence: "DAILY" } })),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["catalog"] });
      void queryClient.invalidateQueries({ queryKey: ["sources"] });
    },
  });
}
