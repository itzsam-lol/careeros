"use client";

import { useQuery } from "@tanstack/react-query";
import { AlarmClock, GitBranch } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { EmptyState, PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { type Schema, unwrap, useApi } from "@/lib/api";
import { type ApplicationStage, STAGES, useUpdateApplication } from "@/lib/careers";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

type Card = Schema<"JobCard">;

const COLUMNS: { title: string; stages: ApplicationStage[] }[] = [
  { title: "Planned", stages: ["PLANNED"] },
  { title: "Applied", stages: ["APPLIED"] },
  { title: "Assessment", stages: ["ASSESSMENT"] },
  { title: "Interview", stages: ["INTERVIEW"] },
  { title: "Offer", stages: ["OFFER", "ACCEPTED"] },
  { title: "Closed", stages: ["REJECTED", "WITHDRAWN"] },
];

function FollowUp({ at }: { at: string | null | undefined }) {
  const [now] = useState(() => Date.now());
  if (!at) return null;
  const days = Math.round((new Date(at).getTime() - now) / 86_400_000);
  const overdue = days <= 0;
  return (
    <span className={cn("inline-flex items-center gap-1 text-xs", overdue ? "font-medium text-destructive" : "text-muted-foreground")}>
      <AlarmClock className="size-3.5" /> {overdue ? (days === 0 ? "Follow up today" : `Follow up overdue ${-days}d`) : `Follow up in ${days}d`}
    </span>
  );
}

function ApplicationCard({ job }: { job: Card }) {
  const update = useUpdateApplication(job.job_id);
  return (
    <article className="glass space-y-2 rounded-xl p-3 text-sm">
      <Link href={`/jobs/${job.job_id}`} className="block font-medium leading-snug hover:underline">
        {job.title}
      </Link>
      <p className="text-muted-foreground">{job.company}</p>
      {job.applied_at ? <p className="text-xs text-muted-foreground">Applied {formatRelative(job.applied_at)}</p> : null}
      <FollowUp at={job.follow_up_at} />
      <select
        aria-label="Application stage"
        className="w-full rounded-lg border border-foreground/10 bg-background px-2 py-1 text-xs"
        value={job.application_stage ?? ""}
        disabled={update.isPending}
        onChange={(event) => update.mutate({ stage: (event.target.value || null) as ApplicationStage | null })}
      >
        {STAGES.map((stage) => (
          <option key={stage.value} value={stage.value}>
            {stage.label}
          </option>
        ))}
        <option value="">Stop tracking</option>
      </select>
    </article>
  );
}

export default function ApplicationsPage() {
  const api = useApi();
  const jobs = useQuery({
    queryKey: ["jobs", "APPLIED", "", "RECENT"],
    queryFn: () => unwrap(api.GET("/api/v1/jobs", { params: { query: { view: "APPLIED", sort: "RECENT", limit: 100, offset: 0 } } })),
  });
  const items = jobs.data?.items ?? [];
  return (
    <>
      <PageHeader title="Applications" description="Track every application from plan to offer. You get a follow-up nudge a week after applying." />
      {jobs.isPending ? (
        <Skeleton className="h-64 rounded-2xl" />
      ) : items.length === 0 ? (
        <EmptyState icon={GitBranch} title="No applications tracked yet" description="Open any job and set its application stage." />
      ) : (
        <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
          {COLUMNS.map((column) => {
            const cards = items.filter((job) => column.stages.includes(job.application_stage as ApplicationStage));
            return (
              <section key={column.title} className="space-y-2">
                <h2 className="flex items-center justify-between text-sm font-semibold">
                  {column.title}
                  <span className="rounded-full bg-foreground/5 px-2 text-xs text-muted-foreground">{cards.length}</span>
                </h2>
                <div className="space-y-2">
                  {cards.map((job) => (
                    <ApplicationCard key={job.job_id} job={job} />
                  ))}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </>
  );
}
