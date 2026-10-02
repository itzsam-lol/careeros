import { useLocalSearchParams } from "expo-router";
import { StyleSheet, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { Card, Chip, EmptyState, Group, Loading, Row, T, type Tone } from "@/components/ui";
import { useJob } from "@/lib/api";
import { usePrep } from "@/lib/careers";
import { useTheme } from "@/lib/theme";

const STATUS: Record<string, { label: string; tone: Tone }> = {
  STRONG: { label: "Strong", tone: "good" },
  RELATED: { label: "Prepare an example", tone: "warn" },
  GAP: { label: "Gap", tone: "bad" },
};

export default function PrepScreen() {
  const theme = useTheme();
  const { colors } = theme;
  const { id } = useLocalSearchParams<{ id: string }>();
  const job = useJob(id);
  const prep = usePrep(id);
  const refresh = useRefresh(() => prep.refetch());

  return (
    <Screen
      back="Job"
      tabBar={false}
      refresh={refresh}
      title="Interview Prep"
      subtitle={job.data ? `${job.data.card.title} at ${job.data.card.company}` : undefined}
    >
      {prep.isPending ? (
        <Loading />
      ) : prep.isError ? (
        <EmptyState icon="alert-circle-outline" title="Couldn't prepare notes" message={prep.error.message} />
      ) : (
        <>
          <View style={[styles.summary, { gap: theme.space.sm }]}>
            {(
              [
                ["Strong", prep.data.summary.strong, colors.success],
                ["Prepare", prep.data.summary.related, colors.warning],
                ["Gaps", prep.data.summary.gaps, colors.danger],
              ] as const
            ).map(([label, value, color]) => (
              <Card key={label} style={{ flex: 1, padding: theme.space.md }}>
                <T v="title2" color={color}>
                  {value}
                </T>
                <T v="caption" color={colors.text2}>
                  {label}
                </T>
              </Card>
            ))}
          </View>

          <View style={{ gap: 7 }}>
            <T v="footnote" color={colors.text2} style={styles.header}>
              What they’ll ask about
            </T>
            {prep.data.talking_points.length === 0 ? (
              <Card>
                <T v="subhead" color={colors.text2}>
                  The posting doesn’t list specific skills. Use the stories below.
                </T>
              </Card>
            ) : (
              prep.data.talking_points.map((point) => (
                <Card key={point.topic}>
                  <View style={{ gap: 8 }}>
                    <View style={styles.between}>
                      <T v="headline">{point.topic}</T>
                      <Chip label={STATUS[point.status]?.label ?? point.status} tone={STATUS[point.status]?.tone ?? "neutral"} />
                    </View>
                    {point.evidence.map((line, index) => (
                      <T key={index} v="subhead">
                        • {line}
                      </T>
                    ))}
                    <T v="footnote" color={colors.text2}>
                      {point.tip}
                    </T>
                  </View>
                </Card>
              ))
            )}
          </View>

          {prep.data.behavioural.length > 0 ? (
            <Group header="Your stories for common questions" footer="Tell each as situation, task, action, result. Every story comes from your verified profile.">
              {prep.data.behavioural.map((item, index) => (
                <Row key={index} title={item.question} subtitle={`${item.where ? `${item.where}: ` : ""}${item.story}`} numberOfLines={3} />
              ))}
            </Group>
          ) : null}

          <Group header="Questions to ask them">
            {prep.data.questions_to_ask.map((question, index) => (
              <Row key={index} title={question} numberOfLines={4} icon="help" iconColor="#5856D6" />
            ))}
          </Group>
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  summary: { flexDirection: "row" },
  between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8 },
  header: { paddingHorizontal: 16, textTransform: "uppercase" },
});
