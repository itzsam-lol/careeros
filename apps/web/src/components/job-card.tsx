"use client";

import { Bookmark, BookmarkCheck, CalendarClock, MapPin, X } from "lucide-react";
import Link from "next/link";

import { MatchLabel, MatchRing } from "@/components/match-ring";
import { Button } from "@/components/ui/button";
import { formatRelative, titleCase } from "@/lib/format";
import { type JobCard, useJobActions } from "@/lib/jobs";
import { cn } from "@/lib/utils";

function deadlineText(deadline: string | null | undefined): { text: string; urgent: boolean } | null {
  if (!deadline) return null;
  const ms = new Date(deadline).getTime() - Date.now();
  if (ms < 0) return { text: "Deadline passed", urgent: false };
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 48) return { text: `Closes in ${hours}h`, urgent: true };
  return { text: `Closes in ${Math.floor(hours / 24)}d`, urgent: hours < 24 * 7 };
}

export function JobCardView({ job, compact = false }: { job: JobCard; compact?: boolean }) {
  const actions = useJobActions(job.job_id);
  const deadline = deadlineText(job.deadline);
  const saved = job.status === "SAVED";
  const match = job.match;

  return (
    <article className="glass group relative rounded-2xl p-4 transition-all hover:-translate-y-0.5 hover:shadow-xl">
      <div className="flex items-start gap-4">
        {match ? (
          <MatchRing score={match.overall_score} eligible={match.eligible} />
        ) : (
          <div className="flex size-12 shrink-0 items-center justify-center rounded-full bg-foreground/5 text-[10px] text-muted-foreground">
            Pending
          </div>
        )}
        <div className="min-w-0 flex-1 space-y-1.5">
          <div className="flex flex-wrap items-center gap-2">
            <Link
              href={`/jobs/${job.job_id}`}
              className="font-semibold leading-snug after:absolute after:inset-0 after:content-[''] hover:underline"
            >
              {job.title}
            </Link>
            {match ? <MatchLabel label={match.label} eligible={match.eligible} /> : null}
          </div>
          <p className="text-sm text-muted-foreground">
            <span className="font-medium text-foreground/80">{job.company}</span>
            {job.location ? (
              <>
                {" · "}
                <MapPin className="mb-0.5 inline size-3.5" aria-hidden /> {job.location}
              </>
            ) : null}
            {job.remote_type !== "UNKNOWN" && !job.location?.toLowerCase().includes(job.remote_type.toLowerCase())
              ? ` · ${titleCase(job.remote_type)}`
              : ""}
            {job.employment_type ? ` · ${titleCase(job.employment_type)}` : ""}
          </p>
          {!compact && match ? (
            <div className="space-y-1 pt-1 text-sm">
              {match.top_strengths[0] ? <p className="line-clamp-1 text-foreground/80">✓ {match.top_strengths[0]}</p> : null}
              {match.top_gaps[0] ? <p className="line-clamp-1 text-muted-foreground">– {match.top_gaps[0]}</p> : null}
            </div>
          ) : null}
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1 pt-1 text-xs text-muted-foreground">
            {deadline ? (
              <span className={cn("inline-flex items-center gap-1", deadline.urgent && "font-medium text-destructive")}>
                <CalendarClock className="size-3.5" aria-hidden /> {deadline.text}
              </span>
            ) : null}
            <span>Found {formatRelative(job.first_seen_at)}</span>
            {job.source_name ? <span>via {job.source_name}</span> : null}
          </div>
        </div>
        <div className="relative z-10 flex shrink-0 flex-col gap-1 opacity-100 transition-opacity md:opacity-0 md:group-hover:opacity-100 md:group-focus-within:opacity-100">
          <Button
            variant="ghost"
            size="icon-sm"
            aria-label={saved ? "Saved" : "Save"}
            onClick={() => (saved ? actions.restore.mutate() : actions.save.mutate())}
          >
            {saved ? <BookmarkCheck className="size-4 text-primary" /> : <Bookmark className="size-4" />}
          </Button>
          {job.status !== "DISMISSED" ? (
            <Button variant="ghost" size="icon-sm" aria-label="Dismiss" onClick={() => actions.dismiss.mutate(undefined)}>
              <X className="size-4" />
            </Button>
          ) : null}
        </div>
      </div>
    </article>
  );
}
