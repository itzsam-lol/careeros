"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  BellRing,
  BriefcaseBusiness,
  CircleCheck,
  CircleX,
  Clock,
  Hourglass,
  Loader,
  Radar,
  RotateCcw,
  Sparkles,
  UserCheck,
} from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState, PageHeader } from "@/components/page-header";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { type Schema, unwrap, useApi } from "@/lib/api";
import { formatRelative, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

type Event = Schema<"EventOut">;
type Task = Schema<"TaskOut">;

const EVENT_ICON: Record<string, React.ComponentType<{ className?: string }>> = {
  DISCOVERY_COMPLETED: Radar,
  DISCOVERY_FAILED: CircleX,
  JOB_DISCOVERED: BriefcaseBusiness,
  JOB_ANALYZED: Activity,
  JOB_MATCHED: Sparkles,
  NOTIFICATION_CREATED: BellRing,
};

const TASK_STATUS: Record<string, { icon: React.ComponentType<{ className?: string }>; className: string }> = {
  QUEUED: { icon: Clock, className: "text-muted-foreground" },
  RUNNING: { icon: Loader, className: "text-primary animate-spin" },
  WAITING_FOR_USER: { icon: UserCheck, className: "text-warning" },
  COMPLETED: { icon: CircleCheck, className: "text-success" },
  FAILED: { icon: CircleX, className: "text-destructive" },
  CANCELLED: { icon: Hourglass, className: "text-muted-foreground" },
};

function dayLabel(iso: string): string {
  const date = new Date(iso);
  const today = new Date();
  const yesterday = new Date(today.getTime() - 86_400_000);
  if (date.toDateString() === today.toDateString()) return "Today";
  if (date.toDateString() === yesterday.toDateString()) return "Yesterday";
  return date.toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "short" });
}

function EventFeed({ events }: { events: Event[] }) {
  const groups = new Map<string, Event[]>();
  for (const event of events) {
    const key = dayLabel(event.created_at);
    groups.set(key, [...(groups.get(key) ?? []), event]);
  }
  return (
    <div className="space-y-6">
      {[...groups.entries()].map(([day, items]) => (
        <section key={day} className="space-y-2">
          <h2 className="px-1 text-sm font-semibold text-muted-foreground">{day}</h2>
          <ol className="glass divide-y divide-foreground/5 rounded-2xl">
            {items.map((event) => {
              const Icon = EVENT_ICON[event.type] ?? Activity;
              const content = (
                <>
                  <Icon className={cn("mt-0.5 size-4 shrink-0", event.type.endsWith("FAILED") ? "text-destructive" : "text-muted-foreground")} />
                  <span className="flex-1">{event.summary}</span>
                  <time className="shrink-0 text-xs text-muted-foreground" dateTime={event.created_at}>
                    {new Date(event.created_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </time>
                </>
              );
              return (
                <li key={event.id}>
                  {event.job_id ? (
                    <Link href={`/jobs/${event.job_id}` as Route} className="flex items-start gap-3 px-4 py-3 text-sm hover:bg-foreground/5">
                      {content}
                    </Link>
                  ) : (
                    <div className="flex items-start gap-3 px-4 py-3 text-sm">{content}</div>
                  )}
                </li>
              );
            })}
          </ol>
        </section>
      ))}
    </div>
  );
}

function TaskList({ tasks }: { tasks: Task[] }) {
  const api = useApi();
  const queryClient = useQueryClient();
  const retry = useMutation({
    mutationFn: (id: string) => unwrap(api.POST("/api/v1/tasks/{task_id}/retry", { params: { path: { task_id: id } } })),
    onSuccess: () => {
      toast.success("Queued again");
      void queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: (error) => toast.error(error.message),
  });
  return (
    <ol className="glass divide-y divide-foreground/5 rounded-2xl">
      {tasks.map((task) => {
        const status = TASK_STATUS[task.status] ?? TASK_STATUS.QUEUED!;
        const Icon = status.icon;
        return (
          <li key={task.id} className="flex items-start gap-3 px-4 py-3 text-sm">
            <Icon className={cn("mt-0.5 size-4 shrink-0", status.className)} />
            <div className="min-w-0 flex-1">
              <p className="font-medium">{titleCase(task.type)}</p>
              <p className="text-xs text-muted-foreground">
                {titleCase(task.status)} · {formatRelative(task.created_at)}
                {task.attempt_count > 1 ? ` · attempt ${task.attempt_count}` : ""}
              </p>
              {task.error ? <p className="mt-1 text-xs text-destructive">{task.error}</p> : null}
            </div>
            {["FAILED", "WAITING_FOR_USER", "CANCELLED"].includes(task.status) ? (
              <Button variant="ghost" size="xs" onClick={() => retry.mutate(task.id)}>
                <RotateCcw className="size-3.5" /> Retry
              </Button>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

export default function ActivityPage() {
  const api = useApi();
  const [tab, setTab] = useState<"activity" | "tasks">("activity");
  const events = useQuery({
    queryKey: ["activity"],
    queryFn: () => unwrap(api.GET("/api/v1/activity", { params: { query: { limit: 200 } } })),
    refetchInterval: 15_000,
  });
  const tasks = useQuery({
    queryKey: ["tasks"],
    queryFn: () => unwrap(api.GET("/api/v1/tasks", { params: { query: { limit: 100 } } })),
    enabled: tab === "tasks",
    refetchInterval: 10_000,
  });

  return (
    <>
      <PageHeader title="Agent activity" description="Everything your career agent did, in order — for transparency and debugging." />
      <div className="glass mb-5 inline-flex rounded-2xl p-1">
        {(["activity", "tasks"] as const).map((value) => (
          <button
            key={value}
            onClick={() => setTab(value)}
            className={cn(
              "rounded-xl px-4 py-1.5 text-sm font-medium transition-colors",
              tab === value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-foreground/5",
            )}
          >
            {value === "activity" ? "Timeline" : "Background tasks"}
          </button>
        ))}
      </div>
      {tab === "activity" ? (
        events.isPending ? (
          <Skeleton className="h-64 rounded-2xl" />
        ) : events.data && events.data.length > 0 ? (
          <EventFeed events={events.data} />
        ) : (
          <EmptyState icon={Activity} title="No activity yet" description="Add a job source and the agent's work shows up here." />
        )
      ) : tasks.isPending ? (
        <Skeleton className="h-64 rounded-2xl" />
      ) : tasks.data && tasks.data.length > 0 ? (
        <TaskList tasks={tasks.data} />
      ) : (
        <EmptyState icon={Clock} title="No background tasks" />
      )}
    </>
  );
}
