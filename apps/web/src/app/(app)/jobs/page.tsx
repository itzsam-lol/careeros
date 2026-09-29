"use client";

import { Inbox, Search, SlidersHorizontal } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { JobCardView } from "@/components/job-card";
import { EmptyState, PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { type JobSort, type JobView, useJobs } from "@/lib/jobs";
import { cn } from "@/lib/utils";

const VIEWS: { value: JobView; label: string; empty: string }[] = [
  { value: "ALL", label: "Inbox", empty: "No open opportunities yet. Add a job source to start discovering." },
  { value: "NEW", label: "New", empty: "Nothing new in the last 7 days." },
  { value: "HIGH_MATCH", label: "High match", empty: "No high matches yet — they appear as soon as the agent finds one." },
  { value: "DEADLINE_SOON", label: "Closing soon", empty: "No deadlines in the next 7 days." },
  { value: "SAVED", label: "Saved", empty: "Save opportunities to build your shortlist." },
  { value: "DISMISSED", label: "Dismissed", empty: "Nothing dismissed." },
  { value: "CLOSED", label: "Closed", empty: "No closed postings." },
];

const SORTS: { value: JobSort; label: string }[] = [
  { value: "SCORE", label: "Best match" },
  { value: "RECENT", label: "Most recent" },
  { value: "DEADLINE", label: "Deadline" },
];

const PAGE = 20;

function JobsInbox() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const view = (VIEWS.find((v) => v.value === params.get("view"))?.value ?? "ALL") as JobView;
  const sort = (SORTS.find((s) => s.value === params.get("sort"))?.value ?? "SCORE") as JobSort;
  const [search, setSearch] = useState(params.get("q") ?? "");
  const [query, setQuery] = useState(search);
  const [limit, setLimit] = useState(PAGE);

  useEffect(() => {
    const handle = setTimeout(() => setQuery(search.trim()), 300);
    return () => clearTimeout(handle);
  }, [search]);

  const jobs = useJobs({ view, sort, q: query, limit });

  function update(next: Record<string, string | null>) {
    const merged = new URLSearchParams(params.toString());
    for (const [key, value] of Object.entries(next)) {
      if (value) merged.set(key, value);
      else merged.delete(key);
    }
    setLimit(PAGE);
    router.replace(`${pathname}?${merged.toString()}` as Route, { scroll: false });
  }

  const current = VIEWS.find((v) => v.value === view) ?? VIEWS[0]!;

  return (
    <>
      <PageHeader
        title="Opportunities"
        description="Jobs, internships and research roles your agent discovered, ranked by how well they fit your verified profile."
        actions={
          <Button variant="outline" asChild>
            <Link href="/settings">
              <SlidersHorizontal className="size-4" /> Sources
            </Link>
          </Button>
        }
      />

      <div className="glass mb-5 flex flex-col gap-3 rounded-2xl p-2 md:flex-row md:items-center">
        <div className="flex gap-1 overflow-x-auto" role="tablist" aria-label="Views">
          {VIEWS.map((item) => (
            <button
              key={item.value}
              role="tab"
              aria-selected={view === item.value}
              onClick={() => update({ view: item.value === "ALL" ? null : item.value })}
              className={cn(
                "shrink-0 rounded-xl px-3 py-1.5 text-sm font-medium transition-colors",
                view === item.value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-foreground/5",
              )}
            >
              {item.label}
            </button>
          ))}
        </div>
        <div className="flex flex-1 gap-2 md:justify-end">
          <div className="relative flex-1 md:max-w-xs">
            <Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="Search title, company, city"
              className="pl-8"
              aria-label="Search opportunities"
            />
          </div>
          <Select value={sort} onValueChange={(value) => update({ sort: value === "SCORE" ? null : value })}>
            <SelectTrigger className="w-36" aria-label="Sort">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {SORTS.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      {jobs.isPending ? (
        <div className="grid gap-3">
          {Array.from({ length: 4 }, (_, i) => (
            <Skeleton key={i} className="h-28 rounded-2xl" />
          ))}
        </div>
      ) : jobs.isError ? (
        <p className="text-sm text-destructive">Could not load opportunities: {jobs.error.message}</p>
      ) : jobs.data.items.length === 0 ? (
        <EmptyState icon={Inbox} title={query ? "No results" : "Nothing here"} description={query ? `Nothing matches “${query}”.` : current.empty} />
      ) : (
        <div className="space-y-3">
          <p className="px-1 text-sm text-muted-foreground">
            {jobs.data.total} {jobs.data.total === 1 ? "opportunity" : "opportunities"}
          </p>
          {jobs.data.items.map((job) => (
            <JobCardView key={job.job_id} job={job} />
          ))}
          {jobs.data.items.length < jobs.data.total ? (
            <div className="flex justify-center pt-2">
              <Button variant="outline" onClick={() => setLimit((n) => n + PAGE)} disabled={jobs.isFetching}>
                {jobs.isFetching ? "Loading…" : "Show more"}
              </Button>
            </div>
          ) : null}
        </div>
      )}
    </>
  );
}

export default function JobsPage() {
  return (
    <Suspense fallback={<Skeleton className="h-40 rounded-2xl" />}>
      <JobsInbox />
    </Suspense>
  );
}
