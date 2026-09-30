import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";

import { storage } from "@/lib/storage";

/**
 * On-device customisation. Everything here is persisted locally and applied instantly;
 * agent behaviour (thresholds, limits, search preferences) lives on the server instead.
 */
export type Accent = "blue" | "indigo" | "purple" | "pink" | "red" | "orange" | "green" | "teal" | "graphite";
export type Canvas = "grouped" | "white" | "warm" | "cool" | "sage";
export type CardStyle = "flat" | "outlined" | "elevated";
export type Corners = "round" | "soft" | "square";
export type TextSize = "xs" | "s" | "m" | "l" | "xl";
export type FontChoice = "inter" | "system" | "serif" | "mono";
export type Density = "comfortable" | "compact";
export type ScoreStyle = "ring" | "badge" | "hidden";
export type HomeSection = "stats" | "alerts" | "topMatches" | "deadlines" | "activity";
export type StartTab = "index" | "jobs" | "alerts" | "profile";
export type JobViewPref = "NEW" | "HIGH_MATCH" | "DEADLINE_SOON" | "SAVED" | "ALL";
export type JobSortPref = "SCORE" | "RECENT" | "DEADLINE";

export interface Prefs {
  // Appearance
  accent: Accent;
  canvas: Canvas;
  cardStyle: CardStyle;
  corners: Corners;
  textSize: TextSize;
  boldText: boolean;
  font: FontChoice;
  density: Density;
  tabLabels: boolean;
  reduceMotion: boolean;
  haptics: boolean;
  // Home
  startTab: StartTab;
  homeOrder: HomeSection[];
  homeHidden: HomeSection[];
  alertsStyle: "stack" | "list";
  greeting: boolean;
  // Jobs & matches
  defaultJobView: JobViewPref;
  jobSort: JobSortPref;
  scoreStyle: ScoreStyle;
  cardInsights: boolean;
  showSalary: boolean;
  showSource: boolean;
  hideIneligible: boolean;
  minScore: number;
  dateStyle: "relative" | "absolute";
  confirmDismiss: boolean;
  openLinks: "in-app" | "browser";
  expandDescription: boolean;
  // Alerts & data
  markReadOnOpen: boolean;
  refreshMinutes: 0 | 1 | 5 | 15;
}

export const DEFAULT_PREFS: Prefs = {
  accent: "blue",
  canvas: "grouped",
  cardStyle: "flat",
  corners: "round",
  textSize: "m",
  boldText: false,
  font: "inter",
  density: "comfortable",
  tabLabels: true,
  reduceMotion: false,
  haptics: true,
  startTab: "index",
  homeOrder: ["stats", "alerts", "topMatches", "deadlines", "activity"],
  homeHidden: [],
  alertsStyle: "stack",
  greeting: true,
  defaultJobView: "NEW",
  jobSort: "SCORE",
  scoreStyle: "ring",
  cardInsights: true,
  showSalary: true,
  showSource: false,
  hideIneligible: false,
  minScore: 0,
  dateStyle: "relative",
  confirmDismiss: true,
  openLinks: "in-app",
  expandDescription: false,
  markReadOnOpen: true,
  refreshMinutes: 1,
};

const KEY = "careeros.prefs";

interface PrefsValue {
  prefs: Prefs;
  ready: boolean;
  set: (patch: Partial<Prefs>) => void;
  reset: (keys?: (keyof Prefs)[]) => void;
}

const PrefsContext = createContext<PrefsValue | null>(null);

function sanitize(raw: unknown): Prefs {
  if (!raw || typeof raw !== "object") return DEFAULT_PREFS;
  const merged = { ...DEFAULT_PREFS } as Record<string, unknown>;
  for (const [key, value] of Object.entries(raw)) {
    // Ignore unknown keys and values whose type no longer matches (older app versions).
    if (key in DEFAULT_PREFS && typeof value === typeof (DEFAULT_PREFS as unknown as Record<string, unknown>)[key]) {
      merged[key] = value;
    }
  }
  const prefs = merged as unknown as Prefs;
  // Keep the section order complete even if new sections were added since it was saved.
  const known = DEFAULT_PREFS.homeOrder;
  const order = Array.isArray(prefs.homeOrder) ? prefs.homeOrder.filter((s) => known.includes(s)) : [];
  prefs.homeOrder = [...order, ...known.filter((s) => !order.includes(s))];
  prefs.homeHidden = Array.isArray(prefs.homeHidden) ? prefs.homeHidden.filter((s) => known.includes(s)) : [];
  return prefs;
}

export function PrefsProvider({ children }: { children: React.ReactNode }) {
  const [prefs, setPrefs] = useState<Prefs>(DEFAULT_PREFS);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    storage
      .get(KEY)
      .then((value) => {
        if (value) setPrefs(sanitize(JSON.parse(value)));
      })
      .catch(() => undefined)
      .finally(() => setReady(true));
  }, []);

  const save = useCallback((next: Prefs) => {
    void storage.set(KEY, JSON.stringify(next)).catch(() => undefined);
  }, []);

  const set = useCallback(
    (patch: Partial<Prefs>) =>
      setPrefs((current) => {
        const next = { ...current, ...patch };
        save(next);
        return next;
      }),
    [save],
  );

  const reset = useCallback(
    (keys?: (keyof Prefs)[]) =>
      setPrefs((current) => {
        const next = { ...current };
        for (const key of keys ?? (Object.keys(DEFAULT_PREFS) as (keyof Prefs)[])) {
          (next as Record<string, unknown>)[key] = DEFAULT_PREFS[key];
        }
        save(next);
        return next;
      }),
    [save],
  );

  const value = useMemo(() => ({ prefs, ready, set, reset }), [prefs, ready, set, reset]);
  return <PrefsContext.Provider value={value}>{children}</PrefsContext.Provider>;
}

export function usePrefs(): PrefsValue {
  const ctx = useContext(PrefsContext);
  if (!ctx) throw new Error("usePrefs must be used inside <PrefsProvider>");
  return ctx;
}
