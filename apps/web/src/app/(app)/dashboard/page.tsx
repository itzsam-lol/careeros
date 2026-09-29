"use client";

import { useQuery } from "@tanstack/react-query";
import {
  Activity,
  BellRing,
  Bookmark,
  CalendarClock,
  Radar,
  Sparkles,
  UserRound,
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import { JobCardView } from "@/components/job-card";
import { NotificationStack } from "@/components/notification-stack";
import { EmptyState, PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { unwrap, useApi } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

function StatTile({
  href,
  label,
  value,
  icon: Icon,
  accent,
}: {
  href: string;
  label: string;
  value: number | string;
  icon: React.ComponentType<{ className?: string }>;
  accent?: string;
}) {
  return (
    <Link href={href as Route} className="glass group rounded-2xl p-4 transition-all hover:-translate-y-0.5 hover:shadow-lg">
      <div className="flex items-center justify-between">
        <span className="text-sm text-muted-foreground">{label}</span>
        <Icon className={cn("size-4 text-muted-foreground", accent)} />
      </div>
      <p className="mt-2 text-3xl font-semibold tabular-nums tracking-tight">{value}</p>
    </Link>
  );
}

export default function DashboardPage() {
  const api = useApi();
  const me = useQuery({ queryKey: ["me"], queryFn: () => unwrap(api.GET("/api/v1/me")) });
  const dashboard = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => unwrap(api.GET("/api/v1/dashboard")),
    refetchInterval: 60_000,
  });

  const firstName = me.data?.name?.split(" ")[0];
  const data = dashboard.data;
  const counts = data?.counts ?? {};

  return (
    <>
      <PageHeader
        title={firstName ? `Welcome back, ${firstName}` : "Dashboard"}
        description={
          data
            ? `${counts.high_match ?? 0} high matches · ${counts.deadline_soon ?? 0} closing this week · ${counts.new ?? 0} new`
            : "Your career agent's view of what matters right now."
        }
      />

      {dashboard.isPending ? (
        <div className="grid gap-4">
          <Skeleton className="h-24 rounded-2xl" />
          <Skeleton className="h-64 rounded-2xl" />
        </div>
      ) : dashboard.isError ? (
        <p className="text-sm text-destructive">Could not reach the CareerOS API: {dashboard.error.message}</p>
      ) : data ? (
        <div className="space-y-6">
          {data.sources.total === 0 || data.profile.completeness < 80 ? (
            <div className="grid gap-3 md:grid-cols-2">
              {data.profile.completeness < 80 ? (
                <div className="glass flex items-center justify-between gap-4 rounded-2xl p-4">
                  <div>
                    <p className="font-medium">Your profile is {data.profile.completeness}% complete</p>
                    <p className="text-sm text-muted-foreground">Matches and resumes only use what you have verified.</p>
                  </div>
                  <Button asChild size="sm">
                    <Link href="/profile">Complete profile</Link>
                  </Button>
                </div>
              ) : null}
              {data.sources.total === 0 ? (
                <div className="glass flex items-center justify-between gap-4 rounded-2xl p-4">
                  <div>
                    <p className="font-medium">No job sources yet</p>
                    <p className="text-sm text-muted-foreground">Add company boards or feeds to start discovering.</p>
                  </div>
                  <Button asChild size="sm">
                    <Link href="/settings">Add a source</Link>
                  </Button>
                </div>
              ) : null}
            </div>
          ) : null}

          <div className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-6">
            <StatTile href="/jobs?view=NEW" label="New" value={counts.new ?? 0} icon={Radar} />
            <StatTile href="/jobs?view=HIGH_MATCH" label="High match" value={counts.high_match ?? 0} icon={Sparkles} accent="text-primary" />
            <StatTile href="/jobs?view=DEADLINE_SOON" label="Closing soon" value={counts.deadline_soon ?? 0} icon={CalendarClock} accent="text-destructive" />
            <StatTile href="/jobs?view=SAVED" label="Saved" value={counts.saved ?? 0} icon={Bookmark} />
            <StatTile href="/activity" label="Unread alerts" value={counts.unread_notifications ?? 0} icon={BellRing} />
            <StatTile href="/profile" label="Profile" value={`${data.profile.completeness}%`} icon={UserRound} />
          </div>

          <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_380px]">
            <section className="min-w-0 space-y-3">
              <div className="flex items-center justify-between">
                <h2 className="text-lg font-semibold">Top matches</h2>
                <Link href="/jobs" className="text-sm text-primary hover:underline">
                  View all
                </Link>
              </div>
              {data.top_matches.length === 0 ? (
                <EmptyState icon={Sparkles} title="No matches yet" description="Matches appear here as soon as the agent analyses new opportunities." />
              ) : (
                data.top_matches.map((job) => <JobCardView key={job.job_id} job={job} />)
              )}
            </section>

            <aside className="space-y-6">
              {data.notifications.length > 0 ? (
                <section className="space-y-2">
                  <h2 className="text-lg font-semibold">Latest for you</h2>
                  <NotificationStack notifications={data.notifications} />
                </section>
              ) : null}
              <section className="space-y-3">
                <h2 className="text-lg font-semibold">Closing soon</h2>
                {data.upcoming_deadlines.length === 0 ? (
                  <p className="glass rounded-2xl p-4 text-sm text-muted-foreground">No deadlines in the next 7 days.</p>
                ) : (
                  data.upcoming_deadlines.map((job) => <JobCardView key={job.job_id} job={job} compact />)
                )}
              </section>
            </aside>
          </div>

          <section className="space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Agent activity</h2>
              <Link href="/activity" className="text-sm text-primary hover:underline">
                See everything
              </Link>
            </div>
            <ol className="glass divide-y divide-foreground/5 rounded-2xl">
              {data.recent_activity.length === 0 ? (
                <li className="p-4 text-sm text-muted-foreground">Nothing yet — the agent logs everything it does here.</li>
              ) : (
                data.recent_activity.map((event) => (
                  <li key={event.id} className="flex items-start gap-3 px-4 py-3 text-sm">
                    <Activity className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
                    <span className="flex-1">{event.summary}</span>
                    <span className="shrink-0 text-xs text-muted-foreground">{formatRelative(event.created_at)}</span>
                  </li>
                ))
              )}
            </ol>
          </section>
        </div>
      ) : null}
    </>
  );
}
