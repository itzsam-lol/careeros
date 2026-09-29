import { CircleCheck, CircleDashed } from "lucide-react";

import type { Schema } from "@/lib/api";
import { cn } from "@/lib/utils";

function Ring({ value }: { value: number }) {
  const radius = 26;
  const circumference = 2 * Math.PI * radius;
  return (
    <svg viewBox="0 0 64 64" className="size-16 -rotate-90" aria-hidden>
      <circle cx="32" cy="32" r={radius} className="fill-none stroke-foreground/10" strokeWidth="6" />
      <circle
        cx="32"
        cy="32"
        r={radius}
        className="fill-none stroke-primary transition-[stroke-dashoffset] duration-700"
        strokeWidth="6"
        strokeLinecap="round"
        strokeDasharray={circumference}
        strokeDashoffset={circumference * (1 - value / 100)}
      />
    </svg>
  );
}

export function CompletenessCard({ stats }: { stats: Schema<"ProfileStats"> }) {
  return (
    <div className="glass space-y-4 rounded-2xl p-4">
      <div className="flex items-center gap-3">
        <div className="relative">
          <Ring value={stats.completeness} />
          <span className="absolute inset-0 flex items-center justify-center text-sm font-semibold">
            {stats.completeness}%
          </span>
        </div>
        <div>
          <p className="font-medium">Profile strength</p>
          <p className="text-xs text-muted-foreground">
            {stats.verified_items} verified · {stats.unverified_items} to review
          </p>
        </div>
      </div>
      <ul className="space-y-2">
        {stats.checklist.map((item) => (
          <li key={item.key} className="flex items-start gap-2 text-sm">
            {item.done ? (
              <CircleCheck className="mt-0.5 size-4 shrink-0 text-success" aria-hidden />
            ) : (
              <CircleDashed className="mt-0.5 size-4 shrink-0 text-muted-foreground" aria-hidden />
            )}
            <span className={cn(item.done && "text-muted-foreground line-through decoration-foreground/20")}>
              {item.label}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
