import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, Pressable, StyleSheet, TextInput, View } from "react-native";

import { Button, Card, Group, Row, Segmented, T } from "@/components/ui";
import { coverageText, STAGES, stageInfo, useApplication, useCreateDocument, useDocuments, useUpdateApplication } from "@/lib/careers";
import { shortDate, useWhen } from "@/lib/format";
import { useTheme } from "@/lib/theme";

const FOLLOW_UPS: { label: string; days: number | null }[] = [
  { label: "3 days", days: 3 },
  { label: "1 week", days: 7 },
  { label: "2 weeks", days: 14 },
  { label: "None", days: null },
];

function inDays(days: number): string {
  const date = new Date();
  date.setDate(date.getDate() + days);
  date.setHours(10, 0, 0, 0);
  return date.toISOString();
}

/** Where the user's application for this job stands: stage, follow-up reminder and notes. */
export function ApplicationCard({ jobId }: { jobId: string }) {
  const theme = useTheme();
  const { colors } = theme;
  const application = useApplication(jobId);
  const update = useUpdateApplication(jobId);
  const [note, setNote] = useState<string | null>(null);
  const data = application.data;
  const current = data?.stage ?? null;
  const noteValue = note ?? data?.note ?? "";

  const setStage = (stage: (typeof STAGES)[number]["value"] | null) => {
    theme.haptic(stage === "OFFER" || stage === "ACCEPTED" ? "success" : "select");
    update.mutate({ stage });
  };

  return (
    <View style={{ gap: 7 }}>
      <View style={styles.headerRow}>
        <T v="footnote" color={colors.text2} style={styles.header}>
          Your application
        </T>
        {update.isPending ? <ActivityIndicator size="small" color={colors.text2} /> : null}
      </View>
      <Card>
        <View style={{ gap: theme.space.md }}>
          <View style={styles.stages}>
            {STAGES.map((stage) => {
              const active = stage.value === current;
              return (
                <Pressable
                  key={stage.value}
                  accessibilityRole="radio"
                  accessibilityState={{ checked: active }}
                  accessibilityLabel={stage.label}
                  onPress={() => setStage(active ? null : stage.value)}
                  style={[
                    styles.stage,
                    { borderRadius: theme.radius.pill, backgroundColor: active ? theme.accent : colors.fill },
                  ]}
                >
                  <T v="subhead" color={active ? "#FFFFFF" : colors.text}>
                    {stage.label}
                  </T>
                </Pressable>
              );
            })}
          </View>
          <T v="footnote" color={colors.text2}>
            {current
              ? `${stageInfo(current)?.label}${data?.applied_at ? ` · applied ${shortDate(data.applied_at)}` : ""}. Tap the stage again to stop tracking.`
              : "Not tracked yet. Pick a stage to add this job to your Tracker."}
          </T>
          {current && ["APPLIED", "ASSESSMENT", "INTERVIEW", "PLANNED"].includes(current) ? (
            <View style={{ gap: 6 }}>
              <T v="subhead">
                Follow-up reminder{data?.follow_up_at ? `: ${shortDate(data.follow_up_at)}` : ""}
              </T>
              <Segmented
                options={FOLLOW_UPS.map((f) => ({ value: f.label, label: f.label }))}
                value={data?.follow_up_at ? "" : "None"}
                onChange={(label) => {
                  const choice = FOLLOW_UPS.find((f) => f.label === label);
                  if (!choice) return;
                  update.mutate(choice.days == null ? { clear_follow_up: true } : { follow_up_at: inDays(choice.days) });
                }}
              />
            </View>
          ) : null}
          <TextInput
            value={noteValue}
            onChangeText={setNote}
            onBlur={() => {
              if (note !== null && note !== (data?.note ?? "")) update.mutate({ note });
            }}
            placeholder="Notes: referral contact, interview dates, recruiter name..."
            placeholderTextColor={colors.text3}
            multiline
            accessibilityLabel="Application notes"
            selectionColor={theme.accent}
            style={[theme.type.callout, styles.note, { color: colors.text, backgroundColor: colors.fill, borderRadius: theme.radius.small }]}
          />
        </View>
      </Card>
    </View>
  );
}

/** Tailored documents for this job, and buttons to create new ones. */
export function JobDocuments({ jobId }: { jobId: string }) {
  const theme = useTheme();
  const when = useWhen();
  const documents = useDocuments(jobId);
  const create = useCreateDocument();
  const [tone, setTone] = useState<"professional" | "warm" | "concise">("professional");

  const start = (kind: "RESUME" | "COVER_LETTER") =>
    create.mutate(
      { kind, jobId, tone },
      {
        onSuccess: (doc) => router.push({ pathname: "/resume/[id]", params: { id: doc.id } }),
        onError: (error) => Alert.alert("Couldn't start", error.message),
      },
    );

  const docs = documents.data ?? [];
  return (
    <View style={{ gap: theme.space.md }}>
      <Group header="Documents for this job" footer="Tailored from your master LaTeX résumé using only verified facts, compiled to one page.">
        <Row title="Tailor Résumé" subtitle="Reorders bullets and skills and picks your most relevant projects" icon="sparkles" iconColor="#007AFF" numberOfLines={2} chevron onPress={() => start("RESUME")} disabled={create.isPending} />
        <Row
          title="Write Cover Letter"
          subtitle="Grounded in your real experience"
          icon="mail"
          iconColor="#FF9500"
          numberOfLines={2}
          chevron
          onPress={() => start("COVER_LETTER")}
          disabled={create.isPending}
          below={
            <Segmented
              options={[
                { value: "professional", label: "Professional" },
                { value: "warm", label: "Warm" },
                { value: "concise", label: "Concise" },
              ]}
              value={tone}
              onChange={setTone}
            />
          }
        />
        {docs.map((doc) => (
          <Row
            key={doc.id}
            title={doc.kind === "COVER_LETTER" ? "Cover letter" : "Tailored résumé"}
            subtitle={[doc.status === "PENDING" ? "Generating…" : doc.status === "FAILED" ? "Failed" : coverageText(doc), when(doc.created_at)].filter(Boolean).join(" · ")}
            icon={doc.kind === "COVER_LETTER" ? "mail-open-outline" : "document-text-outline"}
            iconColor="#8E8E93"
            right={doc.status === "PENDING" ? <ActivityIndicator color={theme.colors.text2} /> : doc.starred ? <Ionicons name="star" size={15} color="#FF9500" /> : undefined}
            chevron
            onPress={() => router.push({ pathname: "/resume/[id]", params: { id: doc.id } })}
          />
        ))}
      </Group>
      <Group header="Get ready">
        <Row title="Interview Prep" subtitle="Talking points, your stories and questions to ask" icon="school" iconColor="#34C759" numberOfLines={2} chevron onPress={() => router.push({ pathname: "/prep/[id]", params: { id: jobId } })} />
        <Row title="Message Drafts" subtitle="Referral request, LinkedIn note, follow-up, thank-you" icon="chatbubbles" iconColor="#5856D6" numberOfLines={2} chevron onPress={() => router.push({ pathname: "/outreach/[id]", params: { id: jobId } })} />
      </Group>
      {create.isPending ? <Button label="Starting…" variant="gray" size="medium" loading onPress={() => undefined} /> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: 16, textTransform: "uppercase" },
  headerRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingRight: 16 },
  stages: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  stage: { paddingHorizontal: 14, paddingVertical: 8 },
  note: { minHeight: 64, padding: 12, textAlignVertical: "top" },
});
