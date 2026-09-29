import { scoreTone } from "@/lib/jobs";
import { cn } from "@/lib/utils";

const TONE_STROKE = {
  strong: "stroke-success",
  good: "stroke-primary",
  partial: "stroke-warning",
  weak: "stroke-muted-foreground",
  ineligible: "stroke-destructive/70",
} as const;

/** Circular relevance score (not a hiring probability). */
export function MatchRing({
  score,
  eligible,
  size = 48,
  className,
}: {
  score: number;
  eligible: boolean;
  size?: number;
  className?: string;
}) {
  const tone = scoreTone(score, eligible);
  const radius = 20;
  const circumference = 2 * Math.PI * radius;
  const percent = Math.round(score * 100);
  return (
    <div
      className={cn("relative shrink-0", className)}
      style={{ width: size, height: size }}
      role="img"
      aria-label={eligible ? `${percent}% match` : `${percent}% match, not eligible`}
    >
      <svg viewBox="0 0 48 48" className="size-full -rotate-90" aria-hidden>
        <circle cx="24" cy="24" r={radius} className="fill-none stroke-foreground/10" strokeWidth="5" />
        <circle
          cx="24"
          cy="24"
          r={radius}
          className={cn("fill-none transition-[stroke-dashoffset] duration-700", TONE_STROKE[tone])}
          strokeWidth="5"
          strokeLinecap="round"
          strokeDasharray={circumference}
          strokeDashoffset={circumference * (1 - score)}
        />
      </svg>
      <span
        className={cn(
          "absolute inset-0 flex items-center justify-center font-semibold tabular-nums",
          size >= 56 ? "text-sm" : "text-xs",
          !eligible && "text-muted-foreground",
        )}
      >
        {percent}
      </span>
    </div>
  );
}

export function MatchLabel({ label, eligible }: { label: string; eligible: boolean }) {
  return (
    <span
      className={cn(
        "rounded-full px-2 py-0.5 text-xs font-medium ring-1 ring-inset",
        eligible ? "bg-primary/10 text-primary ring-primary/20" : "bg-destructive/10 text-destructive ring-destructive/20",
      )}
    >
      {label}
    </span>
  );
}
