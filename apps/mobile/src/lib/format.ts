import { usePrefs } from "@/lib/prefs";

export function titleCase(value: string | null | undefined): string {
  if (!value) return "";
  return value
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/** Workday sends "IN, BANGALORE"; show "IN, Bangalore" (codes such as "NSW" stay as they are). */
export function placeName(value: string): string {
  if (/[a-z]/.test(value)) return value;
  return value
    .split(",")
    .map((part) => (part.trim().length <= 3 ? part : part.replace(/[A-Z]+/g, (word) => word.charAt(0) + word.slice(1).toLowerCase())))
    .join(",");
}

export function relativeTime(iso: string | null | undefined): string {
  if (!iso) return "";
  const diff = Date.now() - new Date(iso).getTime();
  const minutes = Math.round(diff / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.round(hours / 24);
  if (days < 30) return `${days}d ago`;
  return shortDate(iso);
}

export function shortDate(iso: string | null | undefined): string {
  if (!iso) return "";
  const date = new Date(iso);
  const sameYear = date.getFullYear() === new Date().getFullYear();
  return date.toLocaleDateString(undefined, { day: "numeric", month: "short", ...(sameYear ? {} : { year: "numeric" }) });
}

/** Formats timestamps the way the user chose in Settings (relative or calendar dates). */
export function useWhen(): (iso: string | null | undefined) => string {
  const { prefs } = usePrefs();
  return prefs.dateStyle === "absolute" ? shortDate : relativeTime;
}

export function deadlineLabel(iso: string | null | undefined): { text: string; urgent: boolean } | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  if (ms < 0) return { text: "Deadline passed", urgent: false };
  const hours = Math.floor(ms / 3_600_000);
  if (hours < 48) return { text: `Closes in ${hours}h`, urgent: true };
  return { text: `Closes in ${Math.floor(hours / 24)}d`, urgent: hours < 24 * 7 };
}

export function compactMoney(value: number | null | undefined): string {
  if (value == null) return "";
  return new Intl.NumberFormat("en", { notation: "compact", maximumFractionDigits: 1 }).format(value);
}

export function salaryText(
  salary: { minimum: number | null; maximum: number | null; currency: string | null; period: string | null } | null | undefined,
): string | null {
  if (!salary || (!salary.minimum && !salary.maximum)) return null;
  const range =
    salary.minimum === salary.maximum || !salary.maximum || !salary.minimum
      ? compactMoney(salary.minimum ?? salary.maximum)
      : `${compactMoney(salary.minimum)}–${compactMoney(salary.maximum)}`;
  return `${salary.currency ?? ""} ${range}${salary.period ? ` / ${salary.period.toLowerCase()}` : ""}`.trim();
}
