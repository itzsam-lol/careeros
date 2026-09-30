import Ionicons from "@expo/vector-icons/Ionicons";
import { Children, Fragment, isValidElement } from "react";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Switch,
  Text,
  TextInput,
  type TextInputProps,
  type TextStyle,
  View,
  type ViewStyle,
} from "react-native";
import Svg, { Circle } from "react-native-svg";

import { type ScoreStyle } from "@/lib/prefs";
import { scoreColor, type TypeStyle, useTheme } from "@/lib/theme";

export type IconName = keyof typeof Ionicons.glyphMap;

/* ---------- Text ---------- */

export function T({
  v = "body",
  color,
  style,
  numberOfLines,
  children,
  selectable,
}: {
  v?: TypeStyle;
  color?: string;
  style?: TextStyle | TextStyle[];
  numberOfLines?: number;
  children: React.ReactNode;
  selectable?: boolean;
}) {
  const theme = useTheme();
  return (
    <Text
      selectable={selectable}
      numberOfLines={numberOfLines}
      style={[theme.type[v], { color: color ?? theme.colors.text }, style]}
      maxFontSizeMultiplier={1.4}
    >
      {children}
    </Text>
  );
}

/* ---------- Buttons ---------- */

type ButtonVariant = "filled" | "tinted" | "gray" | "plain" | "destructive";

export function Button({
  label,
  onPress,
  variant = "filled",
  size = "large",
  disabled = false,
  loading = false,
  icon,
  style,
}: {
  label: string;
  onPress: () => void;
  variant?: ButtonVariant;
  size?: "large" | "medium" | "small";
  disabled?: boolean;
  loading?: boolean;
  icon?: IconName;
  style?: ViewStyle;
}) {
  const theme = useTheme();
  const { colors } = theme;
  const background = {
    filled: colors.accent,
    tinted: colors.accentSoft,
    gray: colors.fill,
    plain: "transparent",
    destructive: colors.dangerSoft,
  }[variant];
  const color = {
    filled: colors.onAccent,
    tinted: colors.accent,
    gray: colors.text,
    plain: colors.accent,
    destructive: colors.danger,
  }[variant];
  const height = { large: 50, medium: 40, small: 32 }[size];
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ disabled: disabled || loading, busy: loading }}
      disabled={disabled || loading}
      onPress={() => {
        theme.haptic("select");
        onPress();
      }}
      style={({ pressed }) => [
        styles.button,
        {
          height,
          paddingHorizontal: size === "small" ? 12 : 18,
          borderRadius: size === "large" ? theme.radius.control : Math.min(theme.radius.control, height / 2),
          backgroundColor: background,
          opacity: disabled ? 0.4 : pressed ? 0.7 : 1,
        },
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={color} size="small" />
      ) : icon ? (
        <Ionicons name={icon} size={size === "small" ? 15 : 18} color={color} />
      ) : null}
      <Text style={[size === "small" ? theme.type.subhead : theme.type.headline, { color }]} numberOfLines={1}>
        {label}
      </Text>
    </Pressable>
  );
}

export function IconButton({
  icon,
  label,
  onPress,
  tint,
  filled = false,
  size = 36,
  disabled,
}: {
  icon: IconName;
  label: string;
  onPress: () => void;
  tint?: string;
  filled?: boolean;
  size?: number;
  disabled?: boolean;
}) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={label}
      hitSlop={8}
      disabled={disabled}
      onPress={() => {
        theme.haptic("select");
        onPress();
      }}
      style={({ pressed }) => ({
        width: size,
        height: size,
        borderRadius: size / 2,
        alignItems: "center",
        justifyContent: "center",
        backgroundColor: filled ? (tint ?? theme.accent) : theme.colors.fill,
        opacity: disabled ? 0.4 : pressed ? 0.6 : 1,
      })}
    >
      <Ionicons name={icon} size={size * 0.5} color={filled ? "#FFFFFF" : (tint ?? theme.colors.text)} />
    </Pressable>
  );
}

/* ---------- Surfaces ---------- */

export function Card({ children, style, padded = true }: { children: React.ReactNode; style?: ViewStyle; padded?: boolean }) {
  const theme = useTheme();
  return (
    <View style={[theme.card, { borderRadius: theme.radius.card, overflow: "hidden" }, padded && { padding: theme.space.lg }, style]}>
      {children}
    </View>
  );
}

/** iOS inset-grouped list: optional header, rows separated by inset hairlines, optional footer. */
export function Group({
  header,
  footer,
  children,
  action,
}: {
  header?: string;
  footer?: string;
  children: React.ReactNode;
  action?: React.ReactNode;
}) {
  const theme = useTheme();
  const rows = Children.toArray(children).filter((child) => isValidElement(child) || typeof child === "string");
  return (
    <View style={{ gap: 7 }}>
      {header || action ? (
        <View style={styles.groupHeader}>
          {header ? (
            <T v="footnote" color={theme.colors.text2} style={{ textTransform: "uppercase", letterSpacing: 0.2 }}>
              {header}
            </T>
          ) : (
            <View />
          )}
          {action}
        </View>
      ) : null}
      <View style={[theme.card, { borderRadius: theme.radius.card, overflow: "hidden" }]}>
        {rows.map((row, index) => (
          <Fragment key={index}>
            {index > 0 ? <View style={[styles.separator, { backgroundColor: theme.colors.separator, marginLeft: theme.space.lg }]} /> : null}
            {row}
          </Fragment>
        ))}
      </View>
      {footer ? (
        <T v="footnote" color={theme.colors.text2} style={{ paddingHorizontal: theme.space.lg }}>
          {footer}
        </T>
      ) : null}
    </View>
  );
}

export function IconSquare({ icon, color, size = 29 }: { icon: IconName; color: string; size?: number }) {
  const theme = useTheme();
  return (
    <View style={{ width: size, height: size, borderRadius: Math.max(4, theme.radius.small * 0.9), backgroundColor: color, alignItems: "center", justifyContent: "center" }}>
      <Ionicons name={icon} size={size * 0.62} color="#FFFFFF" />
    </View>
  );
}

export function Row({
  title,
  subtitle,
  value,
  icon,
  iconColor,
  onPress,
  chevron,
  checked,
  destructive,
  right,
  left,
  below,
  disabled,
  numberOfLines = 1,
}: {
  title: string;
  subtitle?: string | null;
  value?: string | null;
  icon?: IconName;
  iconColor?: string;
  onPress?: () => void;
  chevron?: boolean;
  checked?: boolean;
  destructive?: boolean;
  right?: React.ReactNode;
  left?: React.ReactNode;
  /** Wide control (e.g. a segmented control) shown full-width under the title. */
  below?: React.ReactNode;
  disabled?: boolean;
  numberOfLines?: number;
}) {
  const theme = useTheme();
  const content = (
    <View style={[styles.row, { minHeight: theme.rowHeight, paddingHorizontal: theme.space.lg, gap: theme.space.md }]}>
      {left}
      {icon ? <IconSquare icon={icon} color={iconColor ?? theme.accent} /> : null}
      <View style={{ flex: 1, paddingVertical: theme.space.sm + 2, gap: 2 }}>
        <T v="body" color={destructive ? theme.colors.danger : theme.colors.text} numberOfLines={numberOfLines}>
          {title}
        </T>
        {subtitle ? (
          <T v="footnote" color={theme.colors.text2} numberOfLines={3}>
            {subtitle}
          </T>
        ) : null}
      </View>
      {value ? (
        <T v="body" color={theme.colors.text2} numberOfLines={1} style={{ maxWidth: "50%", textAlign: "right" }}>
          {value}
        </T>
      ) : null}
      {right}
      {checked ? <Ionicons name="checkmark" size={21} color={theme.accent} /> : null}
      {chevron ? <Ionicons name="chevron-forward" size={18} color={theme.colors.text3} /> : null}
    </View>
  );
  const body = below ? (
    <View>
      {content}
      <View style={{ paddingHorizontal: theme.space.lg, paddingBottom: theme.space.md, marginTop: -2 }}>{below}</View>
    </View>
  ) : (
    content
  );
  if (!onPress) return body;
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityState={{ selected: checked, disabled }}
      disabled={disabled}
      onPress={() => {
        theme.haptic("select");
        onPress();
      }}
      style={({ pressed }) => ({ backgroundColor: pressed ? theme.colors.fill : "transparent", opacity: disabled ? 0.4 : 1 })}
    >
      {body}
    </Pressable>
  );
}

export function Toggle({ value, onChange, label, disabled }: { value: boolean; onChange: (v: boolean) => void; label: string; disabled?: boolean }) {
  const theme = useTheme();
  return (
    <Switch
      accessibilityLabel={label}
      value={value}
      disabled={disabled}
      onValueChange={(next) => {
        theme.haptic("select");
        onChange(next);
      }}
      trackColor={{ true: theme.accent, false: theme.colors.fillStrong }}
      thumbColor="#FFFFFF"
      ios_backgroundColor={theme.colors.fillStrong}
    />
  );
}

export function SwitchRow(props: {
  title: string;
  subtitle?: string;
  value: boolean;
  onChange: (v: boolean) => void;
  icon?: IconName;
  iconColor?: string;
  disabled?: boolean;
}) {
  return (
    <Row
      title={props.title}
      subtitle={props.subtitle}
      icon={props.icon}
      iconColor={props.iconColor}
      numberOfLines={2}
      right={<Toggle value={props.value} onChange={props.onChange} label={props.title} disabled={props.disabled} />}
    />
  );
}

export function Stepper({
  value,
  onChange,
  min,
  max,
  step = 1,
  format = String,
  label,
}: {
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  format?: (v: number) => string;
  label: string;
}) {
  const theme = useTheme();
  const round = (v: number) => Math.round(v * 1000) / 1000;
  return (
    <View style={styles.stepper}>
      <T v="body" color={theme.colors.text2} style={{ minWidth: 48, textAlign: "right", fontVariant: ["tabular-nums"] }}>
        {format(value)}
      </T>
      <View style={[styles.stepperButtons, { backgroundColor: theme.colors.fill, borderRadius: theme.radius.small }]}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Decrease ${label}`}
          disabled={value <= min}
          onPress={() => {
            theme.haptic("select");
            onChange(Math.max(min, round(value - step)));
          }}
          style={[styles.stepperButton, { opacity: value <= min ? 0.3 : 1 }]}
        >
          <Ionicons name="remove" size={20} color={theme.colors.text} />
        </Pressable>
        <View style={{ width: StyleSheet.hairlineWidth, height: 18, backgroundColor: theme.colors.text3 }} />
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={`Increase ${label}`}
          disabled={value >= max}
          onPress={() => {
            theme.haptic("select");
            onChange(Math.min(max, round(value + step)));
          }}
          style={[styles.stepperButton, { opacity: value >= max ? 0.3 : 1 }]}
        >
          <Ionicons name="add" size={20} color={theme.colors.text} />
        </Pressable>
      </View>
    </View>
  );
}

export function StepperRow(props: {
  title: string;
  subtitle?: string;
  value: number;
  onChange: (v: number) => void;
  min: number;
  max: number;
  step?: number;
  format?: (v: number) => string;
}) {
  return (
    <Row
      title={props.title}
      subtitle={props.subtitle}
      numberOfLines={2}
      right={<Stepper label={props.title} value={props.value} onChange={props.onChange} min={props.min} max={props.max} step={props.step} format={props.format} />}
    />
  );
}

/* ---------- Inputs ---------- */

export function Field({
  label,
  hint,
  ref,
  ...props
}: TextInputProps & { label: string; hint?: string; ref?: React.Ref<TextInput> }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 6 }}>
      <T v="footnote" color={theme.colors.text2} style={{ paddingHorizontal: 4 }}>
        {label}
      </T>
      <TextInput
        ref={ref}
        accessibilityLabel={label}
        placeholderTextColor={theme.colors.text3}
        selectionColor={theme.accent}
        {...props}
        style={[
          theme.type.body,
          styles.input,
          { color: theme.colors.text, backgroundColor: theme.colors.fill, borderRadius: theme.radius.control, lineHeight: undefined },
          props.style,
        ]}
      />
      {hint ? (
        <T v="caption" color={theme.colors.text2} style={{ paddingHorizontal: 4 }}>
          {hint}
        </T>
      ) : null}
    </View>
  );
}

export function Segmented<V extends string | number>({
  options,
  value,
  onChange,
}: {
  options: { value: V; label: string }[];
  value: V;
  onChange: (value: V) => void;
}) {
  const theme = useTheme();
  return (
    <View style={[styles.segmented, { backgroundColor: theme.colors.fill, borderRadius: theme.radius.small + 1 }]}>
      {options.map((option) => {
        const active = option.value === value;
        return (
          <Pressable
            key={String(option.value)}
            accessibilityRole="tab"
            accessibilityState={{ selected: active }}
            accessibilityLabel={option.label}
            onPress={() => {
              theme.haptic("select");
              onChange(option.value);
            }}
            style={[
              styles.segment,
              { borderRadius: theme.radius.small - 1 },
              active && [styles.segmentActive, { backgroundColor: "#FFFFFF" }],
            ]}
          >
            <Text
              numberOfLines={1}
              style={[active ? theme.type.headline : theme.type.subhead, { fontSize: theme.type.footnote.fontSize, lineHeight: undefined, color: theme.colors.text }]}
            >
              {option.label}
            </Text>
          </Pressable>
        );
      })}
    </View>
  );
}

/* ---------- Small pieces ---------- */

export type Tone = "neutral" | "accent" | "good" | "warn" | "bad";

export function Chip({ label, tone = "neutral", icon }: { label: string; tone?: Tone; icon?: IconName }) {
  const theme = useTheme();
  const { colors } = theme;
  const [bg, fg] = {
    neutral: [colors.fill, colors.text2],
    accent: [colors.accentSoft, colors.accent],
    good: [colors.successSoft, colors.success],
    warn: [colors.warningSoft, colors.warning],
    bad: [colors.dangerSoft, colors.danger],
  }[tone];
  return (
    <View style={[styles.chip, { backgroundColor: bg, borderRadius: Math.min(theme.radius.pill, 8 + theme.radius.small) }]}>
      {icon ? <Ionicons name={icon} size={12} color={fg} /> : null}
      <T v="caption" color={fg} numberOfLines={1} style={{ flexShrink: 1 }}>
        {label}
      </T>
    </View>
  );
}

export function Score({ score, eligible, size = 44, style: forced }: { score: number; eligible: boolean; size?: number; style?: ScoreStyle }) {
  const theme = useTheme();
  const mode = forced ?? theme.prefs.scoreStyle;
  const percent = Math.round(score * 100);
  const color = scoreColor(theme, score, eligible);
  const a11y = eligible ? `${percent} percent match` : `${percent} percent match, not eligible`;
  if (mode === "hidden") return null;
  if (mode === "badge") {
    return (
      <View accessible accessibilityLabel={a11y} style={[styles.badge, { backgroundColor: theme.colors.fill, borderRadius: theme.radius.small }]}>
        <T v="headline" color={color} style={{ fontVariant: ["tabular-nums"] }}>
          {percent}%
        </T>
      </View>
    );
  }
  const stroke = size >= 64 ? 5 : 3.5;
  const r = (size - stroke) / 2;
  const circumference = 2 * Math.PI * r;
  return (
    <View accessible accessibilityLabel={a11y} style={{ width: size, height: size, alignItems: "center", justifyContent: "center" }}>
      <Svg width={size} height={size} style={StyleSheet.absoluteFill}>
        <Circle cx={size / 2} cy={size / 2} r={r} stroke={theme.colors.fill} strokeWidth={stroke} fill="none" />
        <Circle
          cx={size / 2}
          cy={size / 2}
          r={r}
          stroke={color}
          strokeWidth={stroke}
          fill="none"
          strokeLinecap="round"
          strokeDasharray={`${circumference} ${circumference}`}
          strokeDashoffset={circumference * (1 - score)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`}
        />
      </Svg>
      <Text
        style={[
          theme.type.headline,
          { fontSize: size >= 64 ? 20 : 13, lineHeight: undefined, fontVariant: ["tabular-nums"], color: eligible ? theme.colors.text : theme.colors.text2 },
        ]}
      >
        {percent}
      </Text>
    </View>
  );
}

export function Bar({ value, color }: { value: number; color?: string }) {
  const theme = useTheme();
  return (
    <View style={{ height: 6, borderRadius: 3, backgroundColor: theme.colors.fill, overflow: "hidden" }}>
      <View style={{ width: `${Math.max(0, Math.min(1, value)) * 100}%`, height: "100%", backgroundColor: color ?? theme.accent, borderRadius: 3 }} />
    </View>
  );
}

export function EmptyState({ icon = "file-tray-outline", title, message, action }: { icon?: IconName; title: string; message?: string; action?: React.ReactNode }) {
  const theme = useTheme();
  return (
    <View style={[styles.empty, { padding: theme.space.xl }]}>
      <Ionicons name={icon} size={40} color={theme.colors.text3} />
      <T v="title3" style={{ textAlign: "center" }}>
        {title}
      </T>
      {message ? (
        <T v="subhead" color={theme.colors.text2} style={{ textAlign: "center" }}>
          {message}
        </T>
      ) : null}
      {action ? <View style={{ marginTop: 8 }}>{action}</View> : null}
    </View>
  );
}

export function Loading() {
  const theme = useTheme();
  return <ActivityIndicator color={theme.colors.text2} style={{ marginVertical: 48 }} />;
}

const styles = StyleSheet.create({
  button: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: 8 },
  groupHeader: { flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between", paddingHorizontal: 16, minHeight: 18 },
  separator: { height: StyleSheet.hairlineWidth },
  row: { flexDirection: "row", alignItems: "center" },
  stepper: { flexDirection: "row", alignItems: "center", gap: 10 },
  stepperButtons: { flexDirection: "row", alignItems: "center" },
  stepperButton: { width: 44, height: 32, alignItems: "center", justifyContent: "center" },
  input: { height: 48, paddingHorizontal: 14 },
  segmented: { flexDirection: "row", padding: 2 },
  segment: { flex: 1, alignItems: "center", justifyContent: "center", paddingVertical: 7, paddingHorizontal: 4 },
  segmentActive: { elevation: 1, shadowColor: "#000", shadowOpacity: 0.12, shadowRadius: 4, shadowOffset: { width: 0, height: 1 } },
  chip: { flexDirection: "row", alignItems: "center", gap: 4, paddingHorizontal: 8, paddingVertical: 3, alignSelf: "flex-start", maxWidth: "100%" },
  badge: { paddingHorizontal: 8, paddingVertical: 4, minWidth: 52, alignItems: "center" },
  empty: { alignItems: "center", gap: 8 },
});
