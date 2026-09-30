import Ionicons from "@expo/vector-icons/Ionicons";
import { useState } from "react";
import { Pressable, StyleSheet, TextInput, View } from "react-native";

import { Group, type IconName, Row, T } from "@/components/ui";
import { useTheme } from "@/lib/theme";

/** A group of mutually exclusive rows with a checkmark on the selected one (iOS style). */
export function OptionGroup<V extends string | number>({
  header,
  footer,
  options,
  value,
  onChange,
}: {
  header?: string;
  footer?: string;
  options: { value: V; label: string; subtitle?: string; icon?: IconName; iconColor?: string; left?: React.ReactNode }[];
  value: V;
  onChange: (value: V) => void;
}) {
  return (
    <Group header={header} footer={footer}>
      {options.map((option) => (
        <Row
          key={String(option.value)}
          title={option.label}
          subtitle={option.subtitle}
          icon={option.icon}
          iconColor={option.iconColor}
          right={option.left}
          checked={option.value === value}
          onPress={() => onChange(option.value)}
        />
      ))}
    </Group>
  );
}

/** Editable list of short strings (roles, countries, excluded keywords, ...). */
export function TagEditor({
  header,
  footer,
  values,
  placeholder,
  onChange,
  busy,
}: {
  header: string;
  footer?: string;
  values: string[];
  placeholder: string;
  onChange: (next: string[]) => void;
  busy?: boolean;
}) {
  const theme = useTheme();
  const { colors } = theme;
  const [draft, setDraft] = useState("");

  const add = () => {
    const entries = draft
      .split(",")
      .map((entry) => entry.trim())
      .filter(Boolean)
      .filter((entry) => !values.some((existing) => existing.toLowerCase() === entry.toLowerCase()));
    setDraft("");
    if (entries.length > 0) onChange([...values, ...entries]);
  };

  return (
    <View style={{ gap: 7 }}>
      <T v="footnote" color={colors.text2} style={{ paddingHorizontal: 16, textTransform: "uppercase" }}>
        {header}
      </T>
      <View style={[theme.card, { borderRadius: theme.radius.card, padding: theme.space.md, gap: theme.space.md, opacity: busy ? 0.6 : 1 }]}>
        {values.length > 0 ? (
          <View style={styles.tags}>
            {values.map((value) => (
              <Pressable
                key={value}
                accessibilityRole="button"
                accessibilityLabel={`Remove ${value}`}
                onPress={() => {
                  theme.haptic("light");
                  onChange(values.filter((entry) => entry !== value));
                }}
                style={({ pressed }) => [styles.tag, { backgroundColor: colors.accentSoft, borderRadius: theme.radius.pill, opacity: pressed ? 0.6 : 1 }]}
              >
                <T v="subhead" color={theme.accent}>
                  {value}
                </T>
                <Ionicons name="close" size={14} color={theme.accent} />
              </Pressable>
            ))}
          </View>
        ) : null}
        <View style={[styles.inputRow, { backgroundColor: colors.fill, borderRadius: theme.radius.small + 2 }]}>
          <TextInput
            value={draft}
            onChangeText={setDraft}
            placeholder={placeholder}
            placeholderTextColor={colors.text3}
            selectionColor={theme.accent}
            onSubmitEditing={add}
            returnKeyType="done"
            blurOnSubmit={false}
            accessibilityLabel={`Add to ${header}`}
            style={[theme.type.body, { flex: 1, color: colors.text, paddingVertical: 0, lineHeight: undefined }]}
          />
          <Pressable accessibilityRole="button" accessibilityLabel="Add" disabled={!draft.trim()} onPress={add} hitSlop={8}>
            <Ionicons name="add-circle" size={26} color={draft.trim() ? theme.accent : colors.text3} />
          </Pressable>
        </View>
      </View>
      {footer ? (
        <T v="footnote" color={colors.text2} style={{ paddingHorizontal: 16 }}>
          {footer}
        </T>
      ) : null}
    </View>
  );
}

export function SavingNote({ saving, error }: { saving: boolean; error?: Error | null }) {
  const theme = useTheme();
  if (error) {
    return (
      <T v="footnote" color={theme.colors.danger} style={{ textAlign: "center" }}>
        Couldn't save: {error.message}
      </T>
    );
  }
  if (!saving) return null;
  return (
    <T v="footnote" color={theme.colors.text2} style={{ textAlign: "center" }}>
      Saving…
    </T>
  );
}

const styles = StyleSheet.create({
  tags: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  tag: { flexDirection: "row", alignItems: "center", gap: 4, paddingLeft: 10, paddingRight: 8, paddingVertical: 5 },
  inputRow: { flexDirection: "row", alignItems: "center", gap: 8, height: 40, paddingHorizontal: 10 },
});
