import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, ScrollView, StyleSheet, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { Button, Card, Chip, EmptyState, Loading, T } from "@/components/ui";
import { type JobCard, useJobs } from "@/lib/api";
import { type ApplicationStage, STAGES, stageInfo } from "@/lib/careers";
import { placeName, shortDate, useWhen } from "@/lib/format";
import { openJob } from "@/lib/nav";
import { useTheme } from "@/lib/theme";

type Filter = "ACTIVE" | "ALL" | ApplicationStage;

const ACTIVE: ApplicationStage[] = ["PLANNED", "APPLIED", "ASSESSMENT", "INTERVIEW", "OFFER"];

function followUpState(iso: string | null | undefined): { text: string; overdue: boolean } | null {
  if (!iso) return null;
  const days = Math.round((new Date(iso).getTime() - Date.now()) / 86_400_000);
  if (days < 0) return { text: `Follow up overdue by ${-days}d`, overdue: true };
  if (days === 0) return { text: "Follow up today", overdue: true };
  return { text: `Follow up in ${days}d`, overdue: false };
}

function TrackerCard({ job }: { job: JobCard }) {
  const theme = useTheme();
  const when = useWhen();
  const stage = stageInfo(job.application_stage);
  const follow = followUpState(job.follow_up_at);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${job.title} at ${job.company}, ${stage?.label ?? "tracked"}`}
      onPress={() => openJob(job.job_id, "Tracker")}
      style={({ pressed }) => [theme.card, styles.card, { borderRadius: theme.radius.card, padding: theme.space.lg, opacity: pressed ? 0.75 : 1 }]}
    >
      <View style={{ flex: 1, gap: 3 }}>
        <T v="headline" numberOfLines={2}>
          {job.title}
        </T>
        <T v="subhead" color={theme.colors.text2} numberOfLines={1}>
          {job.company}
          {job.location ? ` · ${placeName(job.location)}` : ""}
        </T>
        <View style={styles.meta}>
          {stage ? <Chip label={stage.label} tone={stage.tone} /> : null}
          {job.applied_at ? <Chip label={`Applied ${shortDate(job.applied_at)}`} icon="paper-plane-outline" /> : null}
          {follow ? <Chip label={follow.text} tone={follow.overdue ? "bad" : "neutral"} icon="alarm-outline" /> : null}
          {job.deadline && !job.applied_at ? <Chip label={`Closes ${when(job.deadline)}`} icon="calendar-outline" /> : null}
        </View>
      </View>
      <Ionicons name="chevron-forward" size={18} color={theme.colors.text3} />
    </Pressable>
  );
}

export default function TrackerScreen() {
  const theme = useTheme();
  const jobs = useJobs("APPLIED", "", "RECENT");
  const refresh = useRefresh(() => jobs.refetch());
  const [filter, setFilter] = useState<Filter>("ACTIVE");
  const all = jobs.data?.pages.flatMap((p) => p.items) ?? [];
  const counts = Object.fromEntries(STAGES.map((s) => [s.value, all.filter((j) => j.application_stage === s.value).length]));
  const shown = all.filter((job) =>
    filter === "ALL" ? true : filter === "ACTIVE" ? ACTIVE.includes(job.application_stage as ApplicationStage) : job.application_stage === filter,
  );
  const overdue = all.filter((j) => followUpState(j.follow_up_at)?.overdue).length;

  const pills: { value: Filter; label: string }[] = [
    { value: "ACTIVE", label: "Active" },
    ...STAGES.filter((s) => counts[s.value] > 0).map((s) => ({ value: s.value as Filter, label: `${s.label} ${counts[s.value]}` })),
    { value: "ALL", label: "All" },
  ];

  return (
    <Screen title="Tracker" subtitle={overdue > 0 ? `${overdue} follow-up${overdue === 1 ? "" : "s"} due` : `${all.length} application${all.length === 1 ? "" : "s"}`} refresh={refresh}>
      {all.length > 0 ? (
        <View style={[styles.funnel, { gap: theme.space.sm }]}>
          {(["APPLIED", "ASSESSMENT", "INTERVIEW", "OFFER"] as ApplicationStage[]).map((stage) => (
            <Card key={stage} style={{ flex: 1, padding: theme.space.md }}>
              <T v="title2" style={{ fontVariant: ["tabular-nums"] }}>
                {counts[stage] ?? 0}
              </T>
              <T v="caption" color={theme.colors.text2} fit>
                {stageInfo(stage)?.label}
              </T>
            </Card>
          ))}
        </View>
      ) : null}

      {all.length > 0 ? (
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={{ gap: 8, paddingHorizontal: 16 }} style={{ marginHorizontal: -16 }}>
          {pills.map((pill) => {
            const active = pill.value === filter;
            return (
              <Pressable
                key={pill.value}
                accessibilityRole="tab"
                accessibilityState={{ selected: active }}
                onPress={() => {
                  theme.haptic("select");
                  setFilter(pill.value);
                }}
                style={[styles.pill, { backgroundColor: active ? theme.colors.text : theme.colors.card, borderRadius: theme.radius.pill }]}
              >
                <T v="subhead" color={active ? "#FFFFFF" : theme.colors.text}>
                  {pill.label}
                </T>
              </Pressable>
            );
          })}
        </ScrollView>
      ) : null}

      {jobs.isPending ? (
        <Loading />
      ) : jobs.isError ? (
        <Card>
          <EmptyState icon="cloud-offline-outline" title="Couldn't load your applications" message={jobs.error.message} action={<Button label="Try Again" variant="tinted" size="medium" onPress={() => void jobs.refetch()} />} />
        </Card>
      ) : all.length === 0 ? (
        <EmptyState
          icon="git-branch-outline"
          title="No applications tracked yet"
          message="Open any job and set its application stage (Planned, Applied, Interview, ...). You'll get a nudge to follow up a week after applying."
          action={<Button label="Browse Jobs" size="medium" onPress={() => router.navigate("/jobs")} />}
        />
      ) : shown.length === 0 ? (
        <EmptyState icon="funnel-outline" title="Nothing here" message="No applications in this stage." />
      ) : (
        <View style={{ gap: theme.space.md }}>
          {shown.map((job) => (
            <TrackerCard key={job.job_id} job={job} />
          ))}
        </View>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  card: { flexDirection: "row", alignItems: "center", gap: 12 },
  meta: { flexDirection: "row", flexWrap: "wrap", gap: 6, marginTop: 6 },
  funnel: { flexDirection: "row" },
  pill: { paddingHorizontal: 14, paddingVertical: 7 },
});
