import { formatDistanceToNowStrict, parseISO } from "date-fns";

const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** "2025-06-01" -> "Jun 2025" (no timezone shifts: dates are calendar dates). */
export function formatMonth(value: string | null | undefined): string | null {
  if (!value) return null;
  const [year, month] = value.split("-");
  const index = Number(month) - 1;
  if (!year || Number.isNaN(index) || index < 0 || index > 11) return value;
  return `${MONTHS[index]} ${year}`;
}

export function formatPeriod(
  start: string | null | undefined,
  end: string | null | undefined,
  isCurrent = false,
): string | null {
  const first = formatMonth(start);
  const last = isCurrent ? "Present" : formatMonth(end);
  if (first && last) return `${first} – ${last}`;
  return first ?? last;
}

export function formatRelative(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    return `${formatDistanceToNowStrict(parseISO(value))} ago`;
  } catch {
    return null;
  }
}

/** API date "YYYY-MM-DD" -> <input type="month"> value "YYYY-MM". */
export function toMonthInput(value: unknown): string {
  return typeof value === "string" && value.length >= 7 ? value.slice(0, 7) : "";
}

/** <input type="month"> value -> API date (first of month) or null. */
export function fromMonthInput(value: string): string | null {
  return /^\d{4}-\d{2}$/.test(value) ? `${value}-01` : null;
}

export function titleCase(value: string): string {
  return value
    .toLowerCase()
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}
