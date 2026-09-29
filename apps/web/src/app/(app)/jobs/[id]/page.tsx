"use client";

import {
  ArrowLeft,
  Bookmark,
  BookmarkCheck,
  CircleAlert,
  CircleCheck,
  CircleDashed,
  CircleX,
  ExternalLink,
  RefreshCw,
  ShieldAlert,
  Undo2,
  X,
} from "lucide-react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { useState } from "react";

import { MatchLabel, MatchRing } from "@/components/match-ring";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatRelative, titleCase } from "@/lib/format";
import { type JobDetail, useJob, useJobActions } from "@/lib/jobs";
import { cn } from "@/lib/utils";

type Match = NonNullable<JobDetail["match"]>;
type Analysis = NonNullable<JobDetail["analysis"]>;

const CHECK_ICON = {
  PASS: <CircleCheck className="size-4 text-success" aria-hidden />,
  FAIL: <CircleX className="size-4 text-destructive" aria-hidden />,
  UNKNOWN: <CircleDashed className="size-4 text-warning" aria-hidden />,
} as const;

const COVERAGE_STYLE: Record<string, string> = {
  MATCHED: "bg-success/12 text-success ring-success/25",
  PARTIAL: "bg-warning/15 text-foreground/80 ring-warning/30",
  MISSING: "bg-foreground/5 text-muted-foreground ring-foreground/10",
};

function Section({ title, children, className }: { title: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={cn("glass space-y-3 rounded-2xl p-5", className)}>
      <h2 className="text-sm font-semibold uppercase tracking-wide text-muted-foreground">{title}</h2>
      {children}
    </section>
  );
}

function money(detail: JobDetail): string | null {
  const salary = detail.card.salary;
  if (!salary || (!salary.minimum && !salary.maximum)) return null;
  const fmt = (n: number | null | undefined) =>
    n == null ? "" : new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(n);
  const range = salary.minimum === salary.maximum ? fmt(salary.minimum) : `${fmt(salary.minimum)}–${fmt(salary.maximum)}`;
  return `${salary.currency ?? ""} ${range}${salary.period ? ` / ${salary.period.toLowerCase()}` : ""}`.trim();
}

function WhyItMatches({ match }: { match: Match }) {
  return (
    <Section title="Why it matches">
      <p className="text-[15px] leading-relaxed">{match.reasoning}</p>
      {match.strengths.length > 0 ? (
        <ul className="space-y-2">
          {match.strengths.map((strength, index) => (
            <li key={index} className="flex gap-2 text-sm">
              <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
              <div className="space-y-1">
                <p>{String(strength.text)}</p>
                {Array.isArray(strength.evidence) && strength.evidence.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {(strength.evidence as { ref: string; title: string }[]).map((ref) => (
                      <Link
                        key={ref.ref}
                        href="/profile"
                        className="rounded-full bg-primary/10 px-2 py-0.5 text-xs text-primary hover:bg-primary/15"
                        title="Evidence from your verified profile"
                      >
                        {ref.title}
                      </Link>
                    ))}
                  </div>
                ) : null}
              </div>
            </li>
          ))}
        </ul>
      ) : null}
    </Section>
  );
}

function GapsAndConcerns({ match }: { match: Match }) {
  if (match.gaps.length === 0 && match.concerns.length === 0) return null;
  return (
    <Section title="Gaps & concerns">
      <ul className="space-y-2 text-sm">
        {match.gaps.map((gap, index) => (
          <li key={`g${index}`} className="flex gap-2">
            <CircleX className="mt-0.5 size-4 shrink-0 text-destructive/80" aria-hidden />
            {String(gap.text)}
          </li>
        ))}
        {match.concerns.map((concern, index) => (
          <li key={`c${index}`} className="flex gap-2 text-muted-foreground">
            <CircleAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
            {concern}
          </li>
        ))}
      </ul>
    </Section>
  );
}

function Coverage({ match }: { match: Match }) {
  const rows = match.requirement_coverage as { skill: string; required: boolean; status: string; note?: string | null }[];
  if (rows.length === 0) return null;
  const group = (required: boolean) => rows.filter((row) => row.required === required);
  return (
    <Section title="Skills the role asks for">
      {[true, false].map((required) =>
        group(required).length > 0 ? (
          <div key={String(required)} className="space-y-1.5">
            <p className="text-xs font-medium text-muted-foreground">{required ? "Required" : "Preferred"}</p>
            <div className="flex flex-wrap gap-1.5">
              {group(required).map((row) => (
                <span
                  key={row.skill}
                  title={row.note ?? titleCase(row.status)}
                  className={cn("rounded-full px-2.5 py-0.5 text-xs font-medium ring-1 ring-inset", COVERAGE_STYLE[row.status])}
                >
                  {row.skill}
                </span>
              ))}
            </div>
          </div>
        ) : null,
      )}
      <p className="text-xs text-muted-foreground">Green: backed by verified evidence · Amber: partial or unverified · Grey: not in your profile</p>
    </Section>
  );
}

function Eligibility({ match }: { match: Match }) {
  if (match.eligibility.length === 0) return null;
  return (
    <Section title="Eligibility">
      <ul className="space-y-2 text-sm">
        {match.eligibility.map((check) => (
          <li key={`${check.key}-${check.detail}`} className="flex gap-2">
            {CHECK_ICON[check.status as keyof typeof CHECK_ICON] ?? CHECK_ICON.UNKNOWN}
            <span>
              <span className="font-medium">{check.label}:</span> {check.detail}
            </span>
          </li>
        ))}
      </ul>
    </Section>
  );
}

function Breakdown({ match }: { match: Match }) {
  const labels: Record<string, string> = {
    skills: "Skills",
    projects: "Projects",
    experience: "Experience",
    research: "Research",
    domain: "Domain",
    preferences: "Your preferences",
  };
  return (
    <Section title="Match breakdown">
      <div className="space-y-2.5">
        {Object.entries(labels).map(([key, label]) => {
          const value = match.dimensions[key] ?? 0;
          return (
            <div key={key} className="space-y-1">
              <div className="flex justify-between text-xs">
                <span>{label}</span>
                <span className="tabular-nums text-muted-foreground">{Math.round(value * 100)}</span>
              </div>
              <div className="h-1.5 rounded-full bg-foreground/10">
                <div className="h-full rounded-full bg-primary transition-all duration-700" style={{ width: `${value * 100}%` }} />
              </div>
            </div>
          );
        })}
      </div>
      <p className="text-xs text-muted-foreground">Relevance to your verified profile — not a prediction of hiring chances.</p>
    </Section>
  );
}

function AtAGlance({ analysis, detail }: { analysis: Analysis; detail: JobDetail }) {
  const rows: [string, string | null][] = [
    ["Seniority", analysis.seniority !== "UNKNOWN" ? titleCase(analysis.seniority ?? "") : null],
    ["Domain", analysis.domain && analysis.domain !== "OTHER" ? titleCase(analysis.domain).replace("Ml Ai", "ML / AI") : null],
    ["Experience", analysis.min_years_experience ? `${analysis.min_years_experience}+ years` : null],
    ["Student role", analysis.requires_current_student ? "Current students" : null],
    ["Graduating", analysis.graduation_years?.length ? analysis.graduation_years.join(", ") : null],
    ["Visa sponsorship", analysis.sponsorship === "UNKNOWN" ? "Not stated" : titleCase(analysis.sponsorship ?? "")],
    ["Compensation", money(detail)],
    ["Apply via", titleCase(detail.card.application_platform)],
  ];
  return (
    <Section title="Role at a glance">
      <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1.5 text-sm">
        {rows
          .filter(([, value]) => value)
          .map(([label, value]) => (
            <div key={label} className="contents">
              <dt className="text-muted-foreground">{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
      </dl>
    </Section>
  );
}

export default function JobDetailPage() {
  const { id } = useParams<{ id: string }>();
  const job = useJob(id);
  const actions = useJobActions(id);
  const [expanded, setExpanded] = useState(false);

  if (job.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-32 rounded-2xl" />
        <Skeleton className="h-64 rounded-2xl" />
      </div>
    );
  }
  if (job.isError) return <p className="text-sm text-destructive">Could not load this job: {job.error.message}</p>;

  const detail = job.data;
  const { card, match, analysis } = detail;
  const saved = card.status === "SAVED";
  const dismissed = card.status === "DISMISSED";

  return (
    <div className="space-y-5">
      <Link href="/jobs" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-4" /> Opportunities
      </Link>

      <header className="glass rounded-2xl p-5 md:p-6">
        <div className="flex flex-col gap-5 md:flex-row md:items-start">
          {match ? <MatchRing score={match.overall_score} eligible={match.eligible} size={72} /> : null}
          <div className="min-w-0 flex-1 space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="text-2xl font-semibold tracking-tight">{card.title}</h1>
              {match ? <MatchLabel label={match.label} eligible={match.eligible} /> : null}
              {!card.is_active ? <span className="rounded-full bg-muted px-2 py-0.5 text-xs">Closed</span> : null}
            </div>
            <p className="text-muted-foreground">
              <span className="font-medium text-foreground">{card.company}</span>
              {card.location ? ` · ${card.location}` : ""}
              {card.remote_type !== "UNKNOWN" ? ` · ${titleCase(card.remote_type)}` : ""}
              {card.employment_type ? ` · ${titleCase(card.employment_type)}` : ""}
            </p>
            <p className="text-xs text-muted-foreground">
              Found {formatRelative(card.first_seen_at)}
              {card.posted_at ? ` · posted ${formatRelative(card.posted_at)}` : ""}
              {card.deadline ? ` · closes ${new Date(card.deadline).toLocaleDateString()}` : ""}
              {match?.stale ? " · match outdated: your profile changed" : ""}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {card.application_url ? (
              <Button asChild>
                <a href={card.application_url} target="_blank" rel="noopener noreferrer">
                  Open posting <ExternalLink className="size-3.5" />
                </a>
              </Button>
            ) : null}
            <Button variant="outline" onClick={() => (saved ? actions.restore.mutate() : actions.save.mutate())}>
              {saved ? <BookmarkCheck className="size-4 text-primary" /> : <Bookmark className="size-4" />}
              {saved ? "Saved" : "Save"}
            </Button>
            {dismissed ? (
              <Button variant="outline" onClick={() => actions.restore.mutate()}>
                <Undo2 className="size-4" /> Restore
              </Button>
            ) : (
              <Button variant="ghost" onClick={() => actions.dismiss.mutate(undefined)}>
                <X className="size-4" /> Dismiss
              </Button>
            )}
            <Button variant="ghost" size="icon" aria-label="Re-match" onClick={() => actions.rematch.mutate()}>
              <RefreshCw className={cn("size-4", actions.rematch.isPending && "animate-spin")} />
            </Button>
          </div>
        </div>
        {analysis?.injection_detected ? (
          <div className="mt-4 flex gap-2 rounded-xl bg-warning/12 p-3 text-sm">
            <ShieldAlert className="mt-0.5 size-4 shrink-0 text-warning" aria-hidden />
            <p>
              This posting contains text addressed to AI assistants (for example, instructions to rate candidates). CareerOS
              ignored it when analysing the role.
            </p>
          </div>
        ) : null}
      </header>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_320px]">
        <div className="min-w-0 space-y-5">
          {match ? (
            <>
              <WhyItMatches match={match} />
              <GapsAndConcerns match={match} />
              <Coverage match={match} />
              <Eligibility match={match} />
            </>
          ) : (
            <Section title="Match">
              <p className="text-sm text-muted-foreground">
                The agent is still analysing this role. Complete your profile if this takes more than a minute.
              </p>
            </Section>
          )}
          <Section title="Job description">
            <div className={cn("relative whitespace-pre-line text-sm leading-relaxed text-foreground/90", !expanded && "max-h-80 overflow-hidden")}>
              {detail.description || "No description provided."}
              {!expanded ? <div className="pointer-events-none absolute inset-x-0 bottom-0 h-20 bg-gradient-to-t from-[var(--glass-bg)] to-transparent" /> : null}
            </div>
            <Button variant="link" className="px-0" onClick={() => setExpanded((v) => !v)}>
              {expanded ? "Show less" : "Show full description"}
            </Button>
          </Section>
        </div>
        <aside className="space-y-5">
          {match ? <Breakdown match={match} /> : null}
          {analysis ? <AtAGlance analysis={analysis} detail={detail} /> : null}
          {analysis && (analysis.responsibilities ?? []).length > 0 ? (
            <Section title="What you'd do">
              <ul className="list-disc space-y-1 pl-4 text-sm">
                {(analysis.responsibilities ?? []).slice(0, 6).map((item) => (
                  <li key={item}>{item}</li>
                ))}
              </ul>
            </Section>
          ) : null}
          <Section title="Seen on">
            <ul className="space-y-2 text-sm">
              {detail.sources.map((source, index) => (
                <li key={index} className="flex items-center justify-between gap-2">
                  <span className="truncate">{source.source_name ?? titleCase(source.source_type)}</span>
                  {source.url ? (
                    <a href={source.url} target="_blank" rel="noopener noreferrer" className="shrink-0 text-primary" aria-label="Open source">
                      <ExternalLink className="size-3.5" />
                    </a>
                  ) : null}
                </li>
              ))}
            </ul>
          </Section>
        </aside>
      </div>
    </div>
  );
}
