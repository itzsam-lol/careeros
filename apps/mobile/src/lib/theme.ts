import * as Haptics from "expo-haptics";
import { useMemo } from "react";
import { Platform, type TextStyle, type ViewStyle } from "react-native";

import { type Accent, type Canvas, type Prefs, usePrefs } from "@/lib/prefs";

/** Apple system colours (light appearance). */
export const ACCENTS: Record<Accent, { label: string; color: string }> = {
  blue: { label: "Blue", color: "#007AFF" },
  indigo: { label: "Indigo", color: "#5856D6" },
  purple: { label: "Purple", color: "#AF52DE" },
  pink: { label: "Pink", color: "#FF2D55" },
  red: { label: "Red", color: "#FF3B30" },
  orange: { label: "Orange", color: "#FF9500" },
  green: { label: "Green", color: "#34C759" },
  teal: { label: "Teal", color: "#30B0C7" },
  graphite: { label: "Graphite", color: "#636366" },
};

export const CANVASES: Record<Canvas, { label: string; background: string; card: string; text: string }> = {
  grouped: { label: "System gray", background: "#F2F2F7", card: "#FFFFFF", text: "#000000" },
  white: { label: "White", background: "#FFFFFF", card: "#F4F4F6", text: "#000000" },
  warm: { label: "Paper", background: "#F5F3EE", card: "#FFFFFF", text: "#1C1A16" },
  cool: { label: "Mist", background: "#EEF1F6", card: "#FFFFFF", text: "#0B1220" },
  sage: { label: "Sage", background: "#EFF3EF", card: "#FFFFFF", text: "#0F1A12" },
};

const TEXT_SCALE = { xs: 0.86, s: 0.93, m: 1, l: 1.1, xl: 1.22 } as const;
const RADIUS_SCALE = { round: 1, soft: 0.6, square: 0.25 } as const;

/** iOS text styles at the default ("Large") content size: [size, line height, weight]. */
const TYPE_SCALE = {
  largeTitle: [34, 41, 700, -0.8],
  title1: [28, 34, 700, -0.6],
  title2: [22, 28, 700, -0.4],
  title3: [20, 25, 600, -0.35],
  headline: [17, 22, 600, -0.3],
  body: [17, 22, 400, -0.3],
  callout: [16, 21, 400, -0.25],
  subhead: [15, 20, 400, -0.2],
  footnote: [13, 18, 400, -0.1],
  caption: [12, 16, 400, 0],
  caption2: [11, 13, 500, 0.05],
} as const;
export type TypeStyle = keyof typeof TYPE_SCALE;
type Weight = 400 | 500 | 600 | 700;

const INTER: Record<Weight, string> = {
  400: "Inter_400Regular",
  500: "Inter_500Medium",
  600: "Inter_600SemiBold",
  700: "Inter_700Bold",
};

function fontFor(prefs: Prefs, weight: Weight): TextStyle {
  const w = (prefs.boldText ? Math.min(700, weight + 100) : weight) as Weight;
  switch (prefs.font) {
    case "inter":
      return { fontFamily: INTER[w] };
    case "serif":
      return { fontFamily: Platform.select({ ios: "Georgia", default: "serif" }), fontWeight: w >= 600 ? "700" : "400" };
    case "mono":
      return { fontFamily: Platform.select({ ios: "Menlo", default: "monospace" }), fontWeight: w >= 600 ? "700" : "400" };
    default:
      return { fontWeight: String(w) as TextStyle["fontWeight"] };
  }
}

function hexToRgba(hex: string, alpha: number): string {
  const n = Number.parseInt(hex.slice(1), 16);
  return `rgba(${(n >> 16) & 255}, ${(n >> 8) & 255}, ${n & 255}, ${alpha})`;
}

export function buildTheme(prefs: Prefs) {
  const canvas = CANVASES[prefs.canvas];
  const accent = ACCENTS[prefs.accent].color;
  const scale = TEXT_SCALE[prefs.textSize];
  const compact = prefs.density === "compact";
  const r = RADIUS_SCALE[prefs.corners];

  const type = Object.fromEntries(
    Object.entries(TYPE_SCALE).map(([name, [size, line, weight, tracking]]) => [
      name,
      {
        fontSize: Math.round(size * scale * 10) / 10,
        lineHeight: Math.round(line * scale),
        letterSpacing: prefs.font === "inter" ? tracking : 0,
        ...fontFor(prefs, weight as Weight),
      } satisfies TextStyle,
    ]),
  ) as Record<TypeStyle, TextStyle>;

  const colors = {
    background: canvas.background,
    card: canvas.card,
    text: canvas.text,
    text2: "rgba(60, 60, 67, 0.64)",
    text3: "rgba(60, 60, 67, 0.36)",
    separator: "rgba(60, 60, 67, 0.16)",
    fill: "rgba(118, 118, 128, 0.12)",
    fillStrong: "rgba(118, 118, 128, 0.2)",
    accent,
    accentSoft: hexToRgba(accent, 0.12),
    onAccent: "#FFFFFF",
    // Accessible (darker) variants of the system colours for text on light backgrounds.
    success: "#248A3D",
    successSoft: "rgba(52, 199, 89, 0.14)",
    warning: "#C93400",
    warningSoft: "rgba(255, 149, 0, 0.14)",
    danger: "#D70015",
    dangerSoft: "rgba(255, 59, 48, 0.12)",
    info: "#0071A4",
    overlay: "rgba(0, 0, 0, 0.3)",
  };

  const cardDecoration: ViewStyle =
    prefs.cardStyle === "outlined"
      ? { borderWidth: 1, borderColor: colors.separator }
      : prefs.cardStyle === "elevated"
        ? Platform.select<ViewStyle>({
            web: { boxShadow: "0 1px 2px rgba(0,0,0,0.04), 0 4px 16px rgba(0,0,0,0.06)" },
            default: { elevation: 2, shadowColor: "#000", shadowOpacity: 0.06, shadowRadius: 12, shadowOffset: { width: 0, height: 4 } },
          })
        : {};

  return {
    prefs,
    colors,
    type,
    accent,
    radius: { card: 14 * r, control: 12 * r, small: 8 * r, pill: 999 },
    space: {
      xs: 4,
      sm: compact ? 6 : 8,
      md: compact ? 10 : 12,
      lg: compact ? 13 : 16,
      xl: compact ? 18 : 24,
      xxl: compact ? 26 : 32,
    },
    rowHeight: compact ? 44 : 52,
    card: { backgroundColor: colors.card, ...cardDecoration } as ViewStyle,
    /** Haptic feedback that respects the user's preference. */
    haptic(kind: "select" | "light" | "success" | "warning" = "select") {
      if (!prefs.haptics || Platform.OS === "web") return;
      if (kind === "select") void Haptics.selectionAsync();
      else if (kind === "light") void Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
      else void Haptics.notificationAsync(kind === "success" ? Haptics.NotificationFeedbackType.Success : Haptics.NotificationFeedbackType.Warning);
    },
  };
}

export type Theme = ReturnType<typeof buildTheme>;

export function useTheme(): Theme {
  const { prefs } = usePrefs();
  return useMemo(() => buildTheme(prefs), [prefs]);
}

export function scoreColor(theme: Theme, score: number, eligible: boolean): string {
  if (!eligible) return theme.colors.danger;
  if (score >= 0.75) return theme.colors.success;
  if (score >= 0.55) return theme.accent;
  if (score >= 0.4) return theme.colors.warning;
  return theme.colors.text3;
}
