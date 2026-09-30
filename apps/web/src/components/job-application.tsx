"use client";

import { FileText, Loader2, Mail, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { coverageText, STAGES, useApplication, useCreateDocument, useDocuments, useOpenPdf, useUpdateApplication } from "@/lib/careers";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

export function ApplicationPanel({ jobId }: { jobId: string }) {
  const application = useApplication(jobId);
  const update = useUpdateApplication(jobId);
  const [note, setNote] = useState<string | null>(null);
  const current = application.data?.stage ?? null;
  const value = note ?? application.data?.note ?? "";
  return (
    <section className="glass space-y-3 rounded-2xl p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Your application</h2>
      <div className="flex flex-wrap gap-1.5">
        {STAGES.map((stage) => (
          <button
            key={stage.value}
            type="button"
            aria-pressed={current === stage.value}
            disabled={update.isPending}
            onClick={() => update.mutate({ stage: current === stage.value ? null : stage.value })}
            className={cn(
              "rounded-full px-3 py-1 text-xs font-medium transition-colors",
              current === stage.value ? "bg-primary text-primary-foreground" : "bg-foreground/5 hover:bg-foreground/10",
            )}
          >
            {stage.label}
          </button>
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        {current
          ? `Tracking since ${application.data?.applied_at ? formatRelative(application.data.applied_at) : "now"}.${application.data?.follow_up_at ? ` Follow up ${formatRelative(application.data.follow_up_at)}.` : ""}`
          : "Pick a stage to add this job to Applications."}
      </p>
      <Textarea
        value={value}
        onChange={(e) => setNote(e.target.value)}
        onBlur={() => {
          if (note !== null && note !== (application.data?.note ?? "")) update.mutate({ note });
        }}
        placeholder="Notes: referral contact, interview dates, recruiter name..."
        rows={3}
      />
    </section>
  );
}

export function DocumentsPanel({ jobId }: { jobId: string }) {
  const documents = useDocuments(jobId);
  const create = useCreateDocument();
  const open = useOpenPdf();
  const [tone, setTone] = useState<"professional" | "warm" | "concise">("professional");
  return (
    <section className="glass space-y-3 rounded-2xl p-5">
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">Documents</h2>
      <div className="grid gap-2">
        <Button onClick={() => create.mutate({ kind: "RESUME", jobId })} disabled={create.isPending}>
          <Sparkles className="size-4" /> Tailor résumé
        </Button>
        <div className="flex gap-2">
          <select
            aria-label="Cover letter tone"
            value={tone}
            onChange={(e) => setTone(e.target.value as typeof tone)}
            className="rounded-md border border-foreground/10 bg-background px-2 text-sm"
          >
            <option value="professional">Professional</option>
            <option value="warm">Warm</option>
            <option value="concise">Concise</option>
          </select>
          <Button variant="outline" className="flex-1" onClick={() => create.mutate({ kind: "COVER_LETTER", jobId, tone })} disabled={create.isPending}>
            <Mail className="size-4" /> Cover letter
          </Button>
        </div>
      </div>
      <ul className="space-y-1.5 text-sm">
        {(documents.data ?? []).map((doc) => (
          <li key={doc.id} className="flex items-center gap-2">
            {doc.kind === "COVER_LETTER" ? <Mail className="size-4 text-warning" /> : <FileText className="size-4 text-primary" />}
            <span className="min-w-0 flex-1 truncate">
              {doc.kind === "COVER_LETTER" ? "Cover letter" : "Résumé"} · {doc.status === "READY" ? coverageText(doc) ?? "ready" : doc.status.toLowerCase()}
            </span>
            {doc.status === "PENDING" ? (
              <Loader2 className="size-4 animate-spin text-muted-foreground" />
            ) : (
              <Button variant="link" size="sm" className="h-auto p-0" disabled={doc.status !== "READY"} onClick={() => open.mutate(doc.id)}>
                Open
              </Button>
            )}
          </li>
        ))}
      </ul>
      <Link href="/resumes" className="text-xs text-primary hover:underline">
        All résumés and letters
      </Link>
    </section>
  );
}
