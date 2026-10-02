import * as Clipboard from "expo-clipboard";
import { useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Alert, StyleSheet, TextInput, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { Button, Card, EmptyState, Group, Loading, Row, T } from "@/components/ui";
import { useJob, useOpenLink } from "@/lib/api";
import { useApplication, useApplyKit, useCreateDocument, useUpdateApplication } from "@/lib/careers";
import { openDocument } from "@/lib/nav";
import { useTheme } from "@/lib/theme";

function useCopy() {
  const theme = useTheme();
  const [copied, setCopied] = useState<string | null>(null);
  const copy = (key: string, text: string) =>
    void Clipboard.setStringAsync(text).then(() => {
      theme.haptic("success");
      setCopied(key);
      setTimeout(() => setCopied((current) => (current === key ? null : current)), 1500);
    });
  return { copied, copy };
}

/** Everything needed to apply to one job: documents, copy-ready answers and a short pitch. */
export default function ApplyKitScreen() {
  const theme = useTheme();
  const { colors } = theme;
  const { id, from } = useLocalSearchParams<{ id: string; from?: string }>();
  const job = useJob(id);
  const kit = useApplyKit(id);
  const application = useApplication(id);
  const update = useUpdateApplication(id);
  const create = useCreateDocument();
  const openLink = useOpenLink();
  const { copied, copy } = useCopy();
  const [pitch, setPitch] = useState<string | null>(null);
  const refresh = useRefresh(() => Promise.all([kit.refetch(), application.refetch()]));
  const data = kit.data;
  const card = job.data?.card;
  const applied = !!application.data?.stage && application.data.stage !== "PLANNED";

  const markApplied = () =>
    update.mutate(
      { stage: "APPLIED" },
      {
        onSuccess: () => {
          theme.haptic("success");
          Alert.alert("Marked as applied", "It's in your Tracker. You'll get a follow-up reminder in a week.");
        },
        onError: (error) => Alert.alert("Couldn't update", error.message),
      },
    );

  return (
    <Screen
      back={from ?? "Job"}
      tabBar={false}
      refresh={refresh}
      title="Apply Kit"
      subtitle={card ? `${card.title} at ${card.company}` : undefined}
    >
      {kit.isPending ? (
        <Loading />
      ) : kit.isError || !data ? (
        <EmptyState icon="alert-circle-outline" title="Couldn't build the kit" message={kit.error?.message} />
      ) : (
        <>
          <View style={{ gap: theme.space.sm }}>
            {data.apply_url ? (
              <Button label="Open Application" icon="open-outline" onPress={() => openLink(data.apply_url as string)} />
            ) : null}
            <Button
              label={applied ? "Applied" : "I've Applied"}
              icon={applied ? "checkmark-circle" : "paper-plane-outline"}
              variant={applied ? "tinted" : "gray"}
              disabled={applied || update.isPending}
              onPress={markApplied}
            />
          </View>

          {data.missing.length > 0 ? (
            <Card>
              <T v="subhead" color={colors.warning}>
                Add your {data.missing.join(", ")} to your profile so forms can be filled from here.
              </T>
            </Card>
          ) : null}

          <Group header="Documents" footer="Attach these where the form asks for a résumé or cover letter.">
            {data.documents.map((doc) => (
              <Row
                key={doc.id}
                title={doc.kind === "COVER_LETTER" ? "Cover letter" : "Tailored résumé"}
                subtitle={doc.title}
                icon={doc.kind === "COVER_LETTER" ? "mail-open-outline" : "document-text-outline"}
                iconColor="#0A84FF"
                chevron
                onPress={() => openDocument(doc.id, "Apply Kit")}
              />
            ))}
            {!data.documents.some((d) => d.kind === "RESUME") ? (
              <Row
                title="Tailor a résumé for this job"
                icon="sparkles"
                iconColor="#0A84FF"
                chevron
                onPress={() => create.mutate({ kind: "RESUME", jobId: id }, { onSuccess: (doc) => openDocument(doc.id, "Apply Kit") })}
              />
            ) : null}
            {!data.documents.some((d) => d.kind === "COVER_LETTER") ? (
              <Row
                title="Write a cover letter"
                icon="mail-open-outline"
                iconColor="#FF9500"
                chevron
                onPress={() => create.mutate({ kind: "COVER_LETTER", jobId: id }, { onSuccess: (doc) => openDocument(doc.id, "Apply Kit") })}
              />
            ) : null}
          </Group>

          <Group header="Tap to copy" footer="From your verified profile.">
            {data.fields.map((field) => (
              <Row
                key={field.label}
                title={field.label}
                subtitle={field.value}
                numberOfLines={3}
                right={<T v="footnote" color={copied === field.label ? colors.success : theme.accent}>{copied === field.label ? "Copied" : "Copy"}</T>}
                onPress={() => copy(field.label, field.value)}
              />
            ))}
          </Group>

          {data.answers.length > 0 ? (
            <Group header="Saved answers">
              {data.answers.map((answer) => (
                <Row
                  key={answer.question}
                  title={answer.question}
                  subtitle={answer.answer}
                  numberOfLines={4}
                  right={<T v="footnote" color={copied === answer.question ? colors.success : theme.accent}>{copied === answer.question ? "Copied" : "Copy"}</T>}
                  onPress={() => copy(answer.question, answer.answer)}
                />
              ))}
            </Group>
          ) : null}

          <View style={{ gap: 7 }}>
            <T v="footnote" color={colors.text2} style={styles.header}>
              Why this company?
            </T>
            <Card>
              <View style={{ gap: 10 }}>
                <TextInput
                  multiline
                  value={pitch ?? data.why_company}
                  onChangeText={setPitch}
                  accessibilityLabel="Why this company draft"
                  selectionColor={theme.accent}
                  style={[theme.type.callout, { color: colors.text, backgroundColor: colors.fill, borderRadius: theme.radius.small, padding: 12, minHeight: 180, textAlignVertical: "top" }]}
                />
                <T v="footnote" color={colors.text2}>
                  A starting point from your verified work. Replace the bracketed part with your own reason.
                </T>
                <Button
                  label={copied === "pitch" ? "Copied" : "Copy"}
                  variant="gray"
                  size="medium"
                  icon={copied === "pitch" ? "checkmark" : "copy-outline"}
                  onPress={() => copy("pitch", pitch ?? data.why_company)}
                />
              </View>
            </Card>
          </View>
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: 16, textTransform: "uppercase" },
});
