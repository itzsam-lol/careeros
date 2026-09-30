import * as Clipboard from "expo-clipboard";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, StyleSheet, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { Bar, Button, Card, Chip, EmptyState, Group, type IconName, Loading, Row, T } from "@/components/ui";
import { useCreateDocument, useDocument, useDocumentActions } from "@/lib/careers";
import { openPdf, sharePdf } from "@/lib/files";
import { useWhen } from "@/lib/format";
import { useTheme } from "@/lib/theme";

const CHANGE_ICONS: Record<string, [IconName, string]> = {
  reorder: ["swap-vertical", "#5856D6"],
  swap_in: ["add-circle", "#34C759"],
  swap_out: ["remove-circle", "#8E8E93"],
  add_skill: ["sparkles", "#007AFF"],
  trim: ["cut", "#FF9500"],
  rephrase: ["create", "#AF52DE"],
  rephrase_rejected: ["shield-checkmark", "#8E8E93"],
  grounded: ["shield-checkmark", "#34C759"],
};

export default function DocumentScreen() {
  const theme = useTheme();
  const { colors } = theme;
  const when = useWhen();
  const { id } = useLocalSearchParams<{ id: string }>();
  const doc = useDocument(id);
  const actions = useDocumentActions(id);
  const regenerate = useCreateDocument();
  const refresh = useRefresh(() => doc.refetch());
  const [busy, setBusy] = useState<"open" | "share" | null>(null);

  if (doc.isPending || doc.isError) {
    return (
      <Screen back="Résumés" tabBar={false} refresh={refresh}>
        {doc.isPending ? <Loading /> : <EmptyState icon="alert-circle-outline" title="Couldn't load this document" message={doc.error.message} />}
      </Screen>
    );
  }

  const d = doc.data;
  const isLetter = d.kind === "COVER_LETTER";
  const title = d.title.replace(/^(Resume|Cover letter) — /, "");

  const withLink = async (mode: "open" | "share") => {
    setBusy(mode);
    try {
      const link = await actions.link.mutateAsync();
      const name = `${isLetter ? "Cover letter" : "Resume"} ${title}`;
      await (mode === "open" ? openPdf(link.url, name) : sharePdf(link.url, name));
    } catch (error) {
      Alert.alert("Couldn't get the PDF", error instanceof Error ? error.message : String(error));
    } finally {
      setBusy(null);
    }
  };

  const remove = () =>
    Alert.alert("Delete this document?", "The PDF and its history are removed. You can generate a new one any time.", [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => actions.remove.mutate(undefined, { onSuccess: () => router.back() }) },
    ]);

  const again = () =>
    regenerate.mutate(
      { kind: d.kind, jobId: d.job_id, tone: (d.options?.tone as "professional" | "warm" | "concise") ?? "professional" },
      { onSuccess: (next) => router.replace({ pathname: "/resume/[id]", params: { id: next.id } }) },
    );

  const hits = Object.entries(d.keywords_after ?? {}) as [string, boolean][];
  const matched = hits.filter(([, ok]) => ok).map(([k]) => k);
  const missing = hits.filter(([, ok]) => !ok).map(([k]) => k);
  const before = d.coverage_before ?? 0;
  const after = d.coverage_after ?? 0;

  return (
    <Screen
      back="Résumés"
      tabBar={false}
      refresh={refresh}
      title={isLetter ? "Cover Letter" : "Tailored Résumé"}
      subtitle={`${title} · ${when(d.created_at)}`}
    >
      {d.status === "PENDING" ? (
        <Card>
          <View style={styles.pending}>
            <ActivityIndicator color={theme.accent} />
            <View style={{ flex: 1 }}>
              <T v="headline">Generating…</T>
              <T v="footnote" color={colors.text2}>
                Tailoring and compiling with LaTeX. This usually takes a few seconds (up to a minute the very first time).
              </T>
            </View>
          </View>
        </Card>
      ) : d.status === "FAILED" ? (
        <Card>
          <View style={{ gap: theme.space.sm }}>
            <T v="headline" color={colors.danger}>
              Couldn't generate this document
            </T>
            <T v="caption" color={colors.text2} selectable numberOfLines={12}>
              {d.error ?? "Unknown error"}
            </T>
            <Button label="Try Again" variant="tinted" size="medium" onPress={again} loading={regenerate.isPending} />
          </View>
        </Card>
      ) : (
        <View style={{ gap: theme.space.sm }}>
          <Button label="Open PDF" icon="document-text-outline" onPress={() => void withLink("open")} loading={busy === "open"} />
          <View style={styles.row}>
            <Button label="Share" variant="gray" icon="share-outline" onPress={() => void withLink("share")} loading={busy === "share"} style={{ flex: 1 }} />
            <Button
              label={d.starred ? "Starred" : "Star"}
              variant="gray"
              icon={d.starred ? "star" : "star-outline"}
              onPress={() => actions.star.mutate(!d.starred)}
              style={{ flex: 1 }}
            />
          </View>
        </View>
      )}

      {!isLetter && d.status === "READY" && hits.length > 0 ? (
        <View style={{ gap: 7 }}>
          <T v="footnote" color={colors.text2} style={styles.header}>
            Skills the job asks for
          </T>
          <Card>
            <View style={{ gap: theme.space.md }}>
              <View style={{ gap: 6 }}>
                <View style={styles.between}>
                  <T v="subhead" color={colors.text2}>
                    Your master résumé
                  </T>
                  <T v="subhead" color={colors.text2}>
                    {Math.round(before * 100)}%
                  </T>
                </View>
                <Bar value={before} color={colors.fillStrong} />
                <View style={styles.between}>
                  <T v="headline">This version</T>
                  <T v="headline" color={after >= 0.75 ? colors.success : theme.accent}>
                    {Math.round(after * 100)}%
                  </T>
                </View>
                <Bar value={after} color={after >= 0.75 ? "#34C759" : theme.accent} />
              </View>
              <View style={styles.chips}>
                {matched.map((k) => (
                  <Chip key={k} label={k} tone="good" icon="checkmark" />
                ))}
                {missing.map((k) => (
                  <Chip key={k} label={k} icon="close" />
                ))}
              </View>
              {missing.length > 0 ? (
                <T v="caption" color={colors.text2}>
                  Gray skills aren't in your verified profile, so they were not added. Nothing on your résumé is invented.
                </T>
              ) : null}
            </View>
          </Card>
        </View>
      ) : null}

      {isLetter && d.body ? (
        <View style={{ gap: 7 }}>
          <T v="footnote" color={colors.text2} style={styles.header}>
            Letter text
          </T>
          <Card>
            <View style={{ gap: theme.space.md }}>
              {d.body.split("\n\n").map((paragraph, index) => (
                <T key={index} v="callout" selectable>
                  {paragraph}
                </T>
              ))}
              <Button
                label="Copy Text"
                variant="gray"
                size="medium"
                icon="copy-outline"
                onPress={() => void Clipboard.setStringAsync(d.body ?? "").then(() => theme.haptic("success"))}
              />
            </View>
          </Card>
        </View>
      ) : null}

      {d.changes.length > 0 ? (
        <Group header={isLetter ? "How it was written" : "What changed"} footer="Every change uses only facts from your verified profile.">
          {d.changes.map((change, index) => {
            const [icon, color] = CHANGE_ICONS[String(change.kind)] ?? ["ellipse", "#8E8E93"];
            return <Row key={index} icon={icon} iconColor={color} title={String(change.detail)} numberOfLines={3} />;
          })}
        </Group>
      ) : null}

      <Group>
        {d.job_id ? (
          <Row title="View Job" icon="briefcase" iconColor="#5856D6" chevron onPress={() => router.push({ pathname: "/job/[id]", params: { id: d.job_id as string } })} />
        ) : null}
        <Row title="Generate Again" icon="refresh" iconColor="#8E8E93" onPress={again} disabled={regenerate.isPending} />
        <Row title="Delete" destructive onPress={remove} />
      </Group>
    </Screen>
  );
}

const styles = StyleSheet.create({
  pending: { flexDirection: "row", gap: 12, alignItems: "center" },
  row: { flexDirection: "row", gap: 8 },
  between: { flexDirection: "row", justifyContent: "space-between" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  header: { paddingHorizontal: 16, textTransform: "uppercase" },
});
