"use client";

import { BellRing, BriefcaseBusiness, CalendarClock, FileText, Send, Sparkles } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";

import type { Schema } from "@/lib/api";
import { formatRelative } from "@/lib/format";
import { cn } from "@/lib/utils";

type Notification = Schema<"NotificationOut">;

const STYLES: Record<string, { icon: React.ComponentType<{ className?: string }>; label: string; tint: string; chip: string }> = {
  HIGH_MATCH: { icon: Sparkles, label: "High match", tint: "text-primary", chip: "bg-primary/15" },
  NEW_JOB: { icon: BriefcaseBusiness, label: "New match", tint: "text-info", chip: "bg-info/15" },
  DEADLINE_SOON: { icon: CalendarClock, label: "Deadline soon", tint: "text-destructive", chip: "bg-destructive/15" },
  RESUME_READY: { icon: FileText, label: "Resume ready", tint: "text-success", chip: "bg-success/15" },
  OUTREACH_APPROVAL_REQUIRED: { icon: Send, label: "Needs approval", tint: "text-warning", chip: "bg-warning/20" },
};
const FALLBACK = { icon: BellRing, label: "Update", tint: "text-foreground", chip: "bg-foreground/10" };

// Positions for back / middle / front cards (front card is the newest).
const POSITIONS = [
  "hover:-translate-y-8 before:absolute before:inset-0 before:rounded-2xl before:bg-background/40 before:transition-opacity before:duration-700 before:content-[''] hover:before:opacity-0 grayscale hover:grayscale-0",
  "translate-x-8 translate-y-6 sm:translate-x-14 sm:translate-y-9 hover:translate-y-0 before:absolute before:inset-0 before:rounded-2xl before:bg-background/40 before:transition-opacity before:duration-700 before:content-[''] hover:before:opacity-0 grayscale hover:grayscale-0",
  "translate-x-16 translate-y-12 sm:translate-x-28 sm:translate-y-[4.5rem] hover:translate-y-8 sm:hover:translate-y-12",
];

function StackCard({ notification, className }: { notification: Notification; className?: string }) {
  const style = STYLES[notification.type] ?? FALLBACK;
  const Icon = style.icon;
  return (
    <Link
      href={(notification.action_url ?? "/dashboard") as Route}
      className={cn(
        // Near-opaque frosted cards: overlapping text from the cards behind must not bleed through.
        "relative flex h-32 w-[16.5rem] -skew-y-[6deg] select-none flex-col justify-between rounded-2xl border border-[var(--glass-border)] bg-card/92 px-4 py-3 shadow-[var(--glass-shadow)] backdrop-blur-xl transition-all duration-700 sm:h-36 sm:w-[21rem] [&>*]:flex [&>*]:items-center [&>*]:gap-2 [grid-area:stack]",
        !notification.read && "ring-1 ring-primary/30",
        className,
      )}
    >
      <div>
        <span className={cn("relative inline-flex rounded-full p-1.5", style.chip)}>
          <Icon className={cn("size-4", style.tint)} />
        </span>
        <p className={cn("text-base font-semibold", style.tint)}>{style.label}</p>
      </div>
      <p className="line-clamp-1 text-[15px] font-medium">{notification.title}</p>
      <p className="text-sm text-muted-foreground">{formatRelative(notification.created_at)}</p>
    </Link>
  );
}

/** Stacked, skewed glass cards for the latest notifications (newest in front). */
export function NotificationStack({ notifications }: { notifications: Notification[] }) {
  const latest = notifications.slice(0, 3).reverse();
  if (latest.length === 0) return null;
  const offset = POSITIONS.length - latest.length;
  return (
    <div className="grid place-items-start pb-16 pl-1 pt-2 [grid-template-areas:'stack'] animate-in fade-in-0 duration-700 sm:pb-20">
      {latest.map((notification, index) => (
        <StackCard key={notification.id} notification={notification} className={POSITIONS[index + offset]} />
      ))}
    </div>
  );
}
