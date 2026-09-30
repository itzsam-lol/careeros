import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";

import { Chip, Score, T, type Tone } from "@/components/ui";
import { type JobCard as Job, useJobAction } from "@/lib/api";
import { stageInfo } from "@/lib/careers";
import { deadlineLabel, salaryText, titleCase, useWhen } from "@/lib/format";
import { useTheme } from "@/lib/theme";

export function locationLine(job: Pick<Job, "company" | "location" | "remote_type" | "employment_type">): string {
  const parts = [job.company];
  if (job.location) parts.push(job.location);
  // Avoid "Remote · Remote" when the location already says it.
  if (job.remote_type !== "UNKNOWN" && !job.location?.toLowerCase().includes(job.remote_type.toLowerCase())) {
    parts.push(titleCase(job.remote_type));
  }
  if (job.employment_type) parts.push(titleCase(job.employment_type));
  return parts.join(" · ");
}

export function matchTone(label: string, eligible: boolean): Tone {
  if (!eligible) return "bad";
  const key = label.toLowerCase();
  if (key.includes("strong")) return "good";
  if (key.includes("good")) return "accent";
  if (key.includes("partial")) return "warn";
  return "neutral";
}

/** Client-side filters from Settings (hide ineligible roles, minimum score). */
export function useJobFilter() {
  const theme = useTheme();
  const { hideIneligible, minScore } = theme.prefs;
  return (job: Job) => {
    if (!job.match) return true;
    if (hideIneligible && !job.match.eligible) return false;
    return job.match.overall_score * 100 >= minScore;
  };
}

export function JobCardView({ job, compact = false }: { job: Job; compact?: boolean }) {
  const theme = useTheme();
  const { prefs, colors } = theme;
  const when = useWhen();
  const action = useJobAction(job.job_id);
  const match = job.match;
  const deadline = deadlineLabel(job.deadline);
  const salary = prefs.showSalary ? salaryText(job.salary) : null;
  const saved = job.status === "SAVED";
  const showScore = match && prefs.scoreStyle !== "hidden";

  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${job.title} at ${job.company}`}
      onPress={() => router.push({ pathname: "/job/[id]", params: { id: job.job_id } })}
      style={({ pressed }) => [
        theme.card,
        { borderRadius: theme.radius.card, padding: theme.space.lg, opacity: pressed ? 0.75 : 1 },
      ]}
    >
      <View style={[styles.row, { gap: theme.space.md }]}>
        {showScore ? <Score score={match.overall_score} eligible={match.eligible} /> : null}
        <View style={styles.body}>
          <T v="headline" numberOfLines={2}>
            {job.title}
          </T>
          <T v="subhead" color={colors.text2} numberOfLines={1}>
            {locationLine(job)}
          </T>
          {!compact && prefs.cardInsights && match ? (
            <View style={{ gap: 2, marginTop: 4 }}>
              {match.top_strengths[0] ? (
                <View style={styles.inline}>
                  <Ionicons name="checkmark-circle" size={15} color={colors.success} />
                  <T v="footnote" numberOfLines={1} style={{ flex: 1 }}>
                    {match.top_strengths[0]}
                  </T>
                </View>
              ) : null}
              {match.top_gaps[0] ? (
                <View style={styles.inline}>
                  <Ionicons name="remove-circle" size={15} color={colors.text3} />
                  <T v="footnote" color={colors.text2} numberOfLines={1} style={{ flex: 1 }}>
                    {match.top_gaps[0]}
                  </T>
                </View>
              ) : null}
            </View>
          ) : null}
          <View style={[styles.meta, { marginTop: theme.space.sm }]}>
            {job.application_stage ? (
              <Chip label={stageInfo(job.application_stage)?.label ?? "Tracked"} tone={stageInfo(job.application_stage)?.tone ?? "accent"} icon="git-network-outline" />
            ) : null}
            {match ? <Chip label={match.label} tone={matchTone(match.label, match.eligible)} /> : <Chip label="Analysing" />}
            {deadline ? <Chip label={deadline.text} tone={deadline.urgent ? "bad" : "neutral"} icon="calendar-outline" /> : null}
            {salary ? <Chip label={salary} icon="cash-outline" /> : null}
            {!deadline ? (
              <T v="caption" color={colors.text2}>
                {when(job.first_seen_at)}
              </T>
            ) : null}
            {prefs.showSource && job.source_name ? (
              <T v="caption" color={colors.text2}>
                via {job.source_name}
              </T>
            ) : null}
          </View>
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={saved ? "Remove from saved" : "Save"}
          hitSlop={10}
          disabled={action.isPending}
          onPress={() => {
            theme.haptic("light");
            action.mutate(saved ? "restore" : "save");
          }}
          style={({ pressed }) => ({ opacity: pressed ? 0.5 : 1, paddingTop: 2 })}
        >
          <Ionicons name={saved ? "bookmark" : "bookmark-outline"} size={21} color={saved ? theme.accent : colors.text3} />
        </Pressable>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignItems: "flex-start" },
  body: { flex: 1, gap: 2, minWidth: 0 },
  inline: { flexDirection: "row", alignItems: "center", gap: 5 },
  meta: { flexDirection: "row", alignItems: "center", flexWrap: "wrap", gap: 6 },
});
