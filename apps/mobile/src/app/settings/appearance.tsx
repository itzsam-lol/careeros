import Ionicons from "@expo/vector-icons/Ionicons";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { Screen } from "@/components/screen";
import { OptionGroup } from "@/components/settings-kit";
import { Button, Card, Chip, Group, Row, Score, Segmented, SwitchRow, T } from "@/components/ui";
import { type Accent, type Canvas, type FontChoice, type TextSize, usePrefs } from "@/lib/prefs";
import { ACCENTS, buildTheme, CANVASES, useTheme } from "@/lib/theme";

const TEXT_SIZES: { value: TextSize; label: string }[] = [
  { value: "xs", label: "XS" },
  { value: "s", label: "S" },
  { value: "m", label: "M" },
  { value: "l", label: "L" },
  { value: "xl", label: "XL" },
];

const FONTS: { value: FontChoice; label: string; subtitle: string }[] = [
  { value: "inter", label: "Inter", subtitle: "Clean and neutral, close to San Francisco" },
  { value: "system", label: "System", subtitle: "Your phone's default typeface" },
  { value: "serif", label: "Serif", subtitle: "Classic, editorial feel" },
  { value: "mono", label: "Monospace", subtitle: "Typewriter look for data lovers" },
];

/** A miniature job card rendered with the current settings. */
function Preview() {
  const theme = useTheme();
  return (
    <View style={{ gap: 7 }}>
      <T v="footnote" color={theme.colors.text2} style={{ paddingHorizontal: 16, textTransform: "uppercase" }}>
        Preview
      </T>
      <View style={[theme.card, { borderRadius: theme.radius.card, padding: theme.space.lg, flexDirection: "row", gap: theme.space.md }]}>
        <Score score={0.82} eligible />
        <View style={{ flex: 1, gap: 2 }}>
          <T v="headline">Machine Learning Intern</T>
          <T v="subhead" color={theme.colors.text2}>
            Nimbus AI · Bengaluru · Hybrid
          </T>
          <View style={{ flexDirection: "row", gap: 6, marginTop: theme.space.sm }}>
            <Chip label="Strong match" tone="good" />
            <Chip label="Closes in 5d" icon="calendar-outline" />
          </View>
        </View>
        <Ionicons name="bookmark" size={21} color={theme.accent} />
      </View>
      <Button label="Primary Button" onPress={() => undefined} />
    </View>
  );
}

export default function AppearanceScreen() {
  const theme = useTheme();
  const { prefs, set, reset } = usePrefs();

  return (
    <Screen title="Appearance" back="Settings" backFallback="/settings" tabBar={false}>
      <Preview />

      <View style={{ gap: 7 }}>
        <T v="footnote" color={theme.colors.text2} style={{ paddingHorizontal: 16, textTransform: "uppercase" }}>
          Accent colour
        </T>
        <Card>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={styles.swatches}>
            {(Object.keys(ACCENTS) as Accent[]).map((key) => {
              const active = prefs.accent === key;
              return (
                <Pressable
                  key={key}
                  accessibilityRole="radio"
                  accessibilityState={{ checked: active }}
                  accessibilityLabel={ACCENTS[key].label}
                  onPress={() => {
                    theme.haptic("select");
                    set({ accent: key });
                  }}
                  style={styles.swatchWrap}
                >
                  <View style={[styles.swatchRing, { borderColor: active ? ACCENTS[key].color : "transparent" }]}>
                    <View style={[styles.swatch, { backgroundColor: ACCENTS[key].color }]}>
                      {active ? <Ionicons name="checkmark" size={18} color="#FFFFFF" /> : null}
                    </View>
                  </View>
                  <T v="caption" color={active ? theme.colors.text : theme.colors.text2}>
                    {ACCENTS[key].label}
                  </T>
                </Pressable>
              );
            })}
          </ScrollView>
        </Card>
      </View>

      <OptionGroup
        header="Background"
        options={(Object.keys(CANVASES) as Canvas[]).map((key) => ({
          value: key,
          label: CANVASES[key].label,
          left: <View style={[styles.canvasDot, { backgroundColor: CANVASES[key].background }]} />,
        }))}
        value={prefs.canvas}
        onChange={(canvas) => set({ canvas })}
      />

      <Group header="Cards & corners">
        <Row
          title="Card style"
          right={
            <View style={{ width: 210 }}>
              <Segmented
                options={[
                  { value: "flat", label: "Flat" },
                  { value: "outlined", label: "Outline" },
                  { value: "elevated", label: "Shadow" },
                ]}
                value={prefs.cardStyle}
                onChange={(cardStyle) => set({ cardStyle })}
              />
            </View>
          }
        />
        <Row
          title="Corners"
          right={
            <View style={{ width: 210 }}>
              <Segmented
                options={[
                  { value: "round", label: "Round" },
                  { value: "soft", label: "Soft" },
                  { value: "square", label: "Square" },
                ]}
                value={prefs.corners}
                onChange={(corners) => set({ corners })}
              />
            </View>
          }
        />
        <Row
          title="Density"
          right={
            <View style={{ width: 210 }}>
              <Segmented
                options={[
                  { value: "comfortable", label: "Comfortable" },
                  { value: "compact", label: "Compact" },
                ]}
                value={prefs.density}
                onChange={(density) => set({ density })}
              />
            </View>
          }
        />
      </Group>

      <View style={{ gap: 7 }}>
        <T v="footnote" color={theme.colors.text2} style={{ paddingHorizontal: 16, textTransform: "uppercase" }}>
          Text size
        </T>
        <Card>
          <View style={{ flexDirection: "row", alignItems: "center", gap: 12 }}>
            <Text style={{ fontSize: 13, color: theme.colors.text2 }}>A</Text>
            <View style={{ flex: 1 }}>
              <Segmented options={TEXT_SIZES} value={prefs.textSize} onChange={(textSize) => set({ textSize })} />
            </View>
            <Text style={{ fontSize: 22, color: theme.colors.text2 }}>A</Text>
          </View>
        </Card>
      </View>

      <Group>
        <SwitchRow title="Bold Text" value={prefs.boldText} onChange={(boldText) => set({ boldText })} />
      </Group>

      <OptionGroup
        header="Font"
        options={FONTS.map((font) => {
          const sample = buildTheme({ ...prefs, font: font.value });
          return {
            value: font.value,
            label: font.label,
            subtitle: font.subtitle,
            left: (
              <View style={[styles.fontSample, { backgroundColor: theme.colors.fill, borderRadius: theme.radius.small }]}>
                <Text style={[sample.type.headline, { color: theme.colors.text, lineHeight: undefined }]}>Aa</Text>
              </View>
            ),
          };
        })}
        value={prefs.font}
        onChange={(font) => set({ font })}
      />

      <Group header="Navigation & motion">
        <SwitchRow title="Tab Bar Labels" value={prefs.tabLabels} onChange={(tabLabels) => set({ tabLabels })} />
        <SwitchRow
          title="Reduce Motion"
          subtitle="Use fades instead of slides and springs."
          value={prefs.reduceMotion}
          onChange={(reduceMotion) => set({ reduceMotion })}
        />
        <SwitchRow title="Haptic Feedback" value={prefs.haptics} onChange={(haptics) => set({ haptics })} />
      </Group>

      <Group>
        <Row
          title="Reset Appearance"
          destructive
          onPress={() =>
            reset(["accent", "canvas", "cardStyle", "corners", "textSize", "boldText", "font", "density", "tabLabels", "reduceMotion", "haptics"])
          }
        />
      </Group>
    </Screen>
  );
}

const styles = StyleSheet.create({
  swatches: { gap: 14, paddingVertical: 2 },
  swatchWrap: { alignItems: "center", gap: 6 },
  swatchRing: { borderWidth: 2, borderRadius: 22, padding: 2 },
  swatch: { width: 34, height: 34, borderRadius: 17, alignItems: "center", justifyContent: "center" },
  canvasDot: { width: 28, height: 28, borderRadius: 14, borderWidth: 1, borderColor: "rgba(0,0,0,0.12)" },
  fontSample: { width: 44, height: 36, alignItems: "center", justifyContent: "center" },
});
