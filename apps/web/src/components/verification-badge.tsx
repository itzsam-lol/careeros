import { CircleAlert, CircleCheck, CircleDashed, CircleX } from "lucide-react";

import { cn } from "@/lib/utils";

const STYLES = {
  VERIFIED: {
    label: "Verified",
    icon: CircleCheck,
    className: "bg-success/12 text-success ring-success/25",
  },
  UNVERIFIED: {
    label: "Needs review",
    icon: CircleDashed,
    className: "bg-warning/15 text-[oklch(0.5_0.13_70)] ring-warning/30 dark:text-warning",
  },
  OUTDATED: {
    label: "Outdated",
    icon: CircleAlert,
    className: "bg-muted text-muted-foreground ring-foreground/10",
  },
  REJECTED: {
    label: "Rejected",
    icon: CircleX,
    className: "bg-destructive/10 text-destructive ring-destructive/20",
  },
} as const;

export type Verification = keyof typeof STYLES;

export function VerificationBadge({ status, className }: { status: Verification; className?: string }) {
  const style = STYLES[status];
  const Icon = style.icon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        style.className,
        className,
      )}
    >
      <Icon className="size-3.5" aria-hidden />
      {style.label}
    </span>
  );
}
