"use client";

import { CircleCheck, FileText, Loader2, Lock, Mail, Sparkles, Star, Trash2, Upload } from "lucide-react";
import Link from "next/link";
import { useRef, useState } from "react";

import { EmptyState, PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import {
  coverageText,
  type DocumentSummary,
  useCreateDocument,
  useDocument,
  useDocumentActions,
  useDocuments,
  useMaster,
  useOpenPdf,
  useUploadMaster,
} from "@/lib/careers";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

const TAILORED = ["experience", "projects", "skills", "leadership", "research"];

function MasterCard() {
  const master = useMaster();
  const upload = useUploadMaster();
  const open = useOpenPdf();
  const create = useCreateDocument();
  const input = useRef<HTMLInputElement>(null);

  const onFile = async (file: File | undefined) => {
    if (!file) return;
    upload.mutate({ tex: await file.text(), filename: file.name.replace(/\.txt$/i, "") });
  };

  const m = master.data;
  return (
    <section className="glass space-y-4 rounded-2xl p-5">
      <input ref={input} type="file" accept=".tex,.txt" className="hidden" onChange={(e) => void onFile(e.target.files?.[0])} />
      {master.isPending ? (
        <Skeleton className="h-32 rounded-xl" />
      ) : !m ? (
        <EmptyState
          icon={Upload}
          title="Upload your LaTeX résumé"
          description="CareerOS tailors a copy for each job: it reorders bullets and skills, swaps in your most relevant projects and keeps it to one page."
          action={
            <Button onClick={() => input.current?.click()} disabled={upload.isPending}>
              {upload.isPending ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />} Choose .tex file
            </Button>
          }
        />
      ) : (
        <div className="grid gap-5 md:grid-cols-[1fr_280px]">
          <div className="space-y-3">
            <div className="flex items-center gap-3">
              <div className="flex size-12 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <FileText className="size-6" />
              </div>
              <div>
                <p className="font-semibold">{m.filename}</p>
                <p className="text-sm text-muted-foreground">
                  Revision {m.revision} · updated {formatRelative(m.updated_at)} ·{" "}
                  {m.compile_error ? <span className="text-destructive">LaTeX error</span> : m.has_pdf ? `compiles to ${m.pages} page${m.pages === 1 ? "" : "s"}` : "compiling…"}
                </p>
              </div>
            </div>
            {m.compile_error ? <pre className="max-h-48 overflow-auto rounded-lg bg-destructive/5 p-3 text-xs text-destructive">{m.compile_error}</pre> : null}
            <ul className="grid gap-1.5 text-sm sm:grid-cols-2">
              {m.sections.map((section, index) => {
                const tailored = TAILORED.includes(String(section.role));
                return (
                  <li key={index} className="flex items-center gap-2">
                    {tailored ? <Sparkles className="size-3.5 text-primary" /> : <Lock className="size-3.5 text-muted-foreground" />}
                    <span>{String(section.title)}</span>
                  </li>
                );
              })}
            </ul>
            <p className="text-xs text-muted-foreground">Sparkles mark the sections tailored for each job. Everything else stays exactly as you wrote it.</p>
          </div>
          <div className="flex flex-col gap-2">
            <Button onClick={() => open.mutate(null)} disabled={!m.has_pdf || open.isPending} variant="outline">
              <FileText className="size-4" /> View PDF
            </Button>
            <Button onClick={() => input.current?.click()} variant="outline" disabled={upload.isPending}>
              {upload.isPending ? <Loader2 className="size-4 animate-spin" /> : <Upload className="size-4" />} Replace .tex
            </Button>
            <Button onClick={() => create.mutate({ kind: "RESUME", jobId: null })} disabled={!m.has_pdf || create.isPending}>
              <Sparkles className="size-4" /> Generate general version
            </Button>
          </div>
        </div>
      )}
    </section>
  );
}

function DocumentDetails({ id }: { id: string }) {
  const doc = useDocument(id);
  if (doc.isPending) return <Skeleton className="h-24 rounded-xl" />;
  if (doc.isError) return <p className="text-sm text-destructive">{doc.error.message}</p>;
  const d = doc.data;
  const hits = Object.entries(d.keywords_after ?? {}) as [string, boolean][];
  return (
    <div className="space-y-4 border-t border-foreground/5 px-4 pb-4 pt-3 text-sm">
      {hits.length > 0 ? (
        <div className="flex flex-wrap gap-1.5">
          {hits.map(([skill, ok]) => (
            <span key={skill} className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium", ok ? "bg-success/12 text-success" : "bg-foreground/5 text-muted-foreground")}>
              {ok ? "✓" : "×"} {skill}
            </span>
          ))}
        </div>
      ) : null}
      {d.body ? <div className="whitespace-pre-line rounded-lg bg-foreground/[0.03] p-3 leading-relaxed">{d.body}</div> : null}
      <ul className="space-y-1.5">
        {d.changes.map((change, index) => (
          <li key={index} className="flex gap-2">
            <CircleCheck className="mt-0.5 size-4 shrink-0 text-primary" />
            <span>{String(change.detail)}</span>
          </li>
        ))}
      </ul>
      {d.error ? <pre className="max-h-40 overflow-auto text-xs text-destructive">{d.error}</pre> : null}
    </div>
  );
}

function DocumentRow({ doc, expanded, onToggle }: { doc: DocumentSummary; expanded: boolean; onToggle: () => void }) {
  const open = useOpenPdf();
  const { star, remove } = useDocumentActions();
  const letter = doc.kind === "COVER_LETTER";
  const title = doc.title.replace(/^(Resume|Cover letter) — /, "");
  return (
    <li className="glass overflow-hidden rounded-2xl">
      <div className="flex items-center gap-3 p-4">
        <div className={cn("flex size-10 shrink-0 items-center justify-center rounded-xl", letter ? "bg-warning/15 text-warning" : "bg-primary/10 text-primary")}>
          {letter ? <Mail className="size-5" /> : <FileText className="size-5" />}
        </div>
        <button type="button" className="min-w-0 flex-1 text-left" onClick={onToggle}>
          <p className="truncate font-medium">{title}</p>
          <p className="text-sm text-muted-foreground">
            {letter ? "Cover letter" : "Résumé"} · {doc.status === "PENDING" ? "generating…" : doc.status === "FAILED" ? "failed" : coverageText(doc) ?? "ready"} · {formatRelative(doc.created_at)}
          </p>
        </button>
        {doc.status === "PENDING" ? <Loader2 className="size-4 animate-spin text-muted-foreground" /> : null}
        {doc.job_id ? (
          <Button asChild variant="ghost" size="sm">
            <Link href={`/jobs/${doc.job_id}`}>Job</Link>
          </Button>
        ) : null}
        <Button variant="ghost" size="icon-sm" aria-label={doc.starred ? "Unstar" : "Star"} onClick={() => star.mutate({ id: doc.id, starred: !doc.starred })}>
          <Star className={cn("size-4", doc.starred && "fill-warning text-warning")} />
        </Button>
        <Button variant="outline" size="sm" disabled={doc.status !== "READY" || open.isPending} onClick={() => open.mutate(doc.id)}>
          Open PDF
        </Button>
        <Button variant="ghost" size="icon-sm" aria-label="Delete" onClick={() => remove.mutate(doc.id)}>
          <Trash2 className="size-4" />
        </Button>
      </div>
      {expanded ? <DocumentDetails id={doc.id} /> : null}
    </li>
  );
}

export default function ResumesPage() {
  const documents = useDocuments();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [filter, setFilter] = useState<"all" | "RESUME" | "COVER_LETTER" | "starred">("all");
  const all = documents.data ?? [];
  const shown = all.filter((d) => (filter === "all" ? true : filter === "starred" ? d.starred : d.kind === filter));
  return (
    <>
      <PageHeader title="Résumés" description="Your master LaTeX résumé and every tailored version and cover letter, built only from verified facts." />
      <div className="space-y-6">
        <MasterCard />
        <div className="flex flex-wrap gap-2">
          {(
            [
              ["all", "All"],
              ["RESUME", "Résumés"],
              ["COVER_LETTER", "Cover letters"],
              ["starred", "Starred"],
            ] as const
          ).map(([value, label]) => (
            <Button key={value} size="sm" variant={filter === value ? "default" : "outline"} onClick={() => setFilter(value)}>
              {label}
            </Button>
          ))}
        </div>
        {documents.isPending ? (
          <Skeleton className="h-40 rounded-2xl" />
        ) : shown.length === 0 ? (
          <EmptyState icon={FileText} title="No documents yet" description="Open any job and choose Tailor résumé or Cover letter." />
        ) : (
          <ul className="space-y-3">
            {shown.map((doc) => (
              <DocumentRow key={doc.id} doc={doc} expanded={expanded === doc.id} onToggle={() => setExpanded(expanded === doc.id ? null : doc.id)} />
            ))}
          </ul>
        )}
      </div>
    </>
  );
}
