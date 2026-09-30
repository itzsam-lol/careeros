import Ionicons from "@expo/vector-icons/Ionicons";
import { useState } from "react";
import { ActivityIndicator, Alert, StyleSheet, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { Button, Card, Chip, EmptyState, Group, Loading, Row, Segmented, T } from "@/components/ui";
import {
  coverageText,
  type DocumentSummary,
  useCreateDocument,
  useDocuments,
  useMaster,
  useMasterLink,
  useUploadMaster,
} from "@/lib/careers";
import { openPdf, pickTexFile } from "@/lib/files";
import { useWhen } from "@/lib/format";
import { openDocument } from "@/lib/nav";
import { useTheme } from "@/lib/theme";

const TAILORED_ROLES = ["experience", "projects", "skills", "leadership", "research"];

function DocumentRow({ doc }: { doc: DocumentSummary }) {
  const theme = useTheme();
  const when = useWhen();
  const isLetter = doc.kind === "COVER_LETTER";
  const status = doc.status === "PENDING" ? "Generating…" : doc.status === "FAILED" ? "Failed" : coverageText(doc);
  return (
    <Row
      title={doc.title.replace(/^(Resume|Cover letter) — /, "")}
      subtitle={[isLetter ? "Cover letter" : "Résumé", status, when(doc.created_at)].filter(Boolean).join(" · ")}
      icon={isLetter ? "mail" : "document-text"}
      iconColor={doc.status === "FAILED" ? "#FF3B30" : isLetter ? "#FF9500" : "#007AFF"}
      numberOfLines={2}
      right={
        doc.status === "PENDING" ? (
          <ActivityIndicator color={theme.colors.text2} />
        ) : doc.starred ? (
          <Ionicons name="star" size={16} color="#FF9500" />
        ) : undefined
      }
      chevron
      onPress={() => openDocument(doc.id, "Résumés")}
    />
  );
}

export default function ResumesScreen() {
  const theme = useTheme();
  const { colors } = theme;
  const when = useWhen();
  const master = useMaster();
  const upload = useUploadMaster();
  const link = useMasterLink();
  const documents = useDocuments();
  const create = useCreateDocument();
  const refresh = useRefresh(() => Promise.all([master.refetch(), documents.refetch()]));
  const [filter, setFilter] = useState<"all" | "RESUME" | "COVER_LETTER" | "starred">("all");

  const replaceMaster = async () => {
    try {
      const picked = await pickTexFile();
      if (!picked) return;
      upload.mutate({ tex: picked.text, filename: picked.name }, { onSuccess: () => theme.haptic("success") });
    } catch (error) {
      Alert.alert("Couldn't use that file", error instanceof Error ? error.message : String(error));
    }
  };

  const viewMaster = () =>
    link.mutate(undefined, {
      onSuccess: (result) => void openPdf(result.url, "Resume").catch((error: Error) => Alert.alert("Couldn't open the PDF", error.message)),
      onError: (error) => Alert.alert("Couldn't open the PDF", error.message),
    });

  const generateGeneral = () =>
    create.mutate({ kind: "RESUME", jobId: null }, { onSuccess: (doc) => openDocument(doc.id, "Résumés") });

  const all = documents.data ?? [];
  const shown = all.filter((d) => (filter === "all" ? true : filter === "starred" ? d.starred : d.kind === filter));
  const m = master.data;

  return (
    <Screen title="Résumés" refresh={refresh}>
      <View style={{ gap: 7 }}>
        <T v="footnote" color={colors.text2} style={{ paddingHorizontal: 16, textTransform: "uppercase" }}>
          Master résumé
        </T>
        <Card>
          {master.isPending ? (
            <Loading />
          ) : !m ? (
            <EmptyState
              icon="document-attach-outline"
              title="Add your LaTeX résumé"
              message="CareerOS tailors a copy for every job: it reorders your bullets and skills, swaps in your most relevant projects and keeps it to one page."
              action={<Button label="Choose .tex File" size="medium" onPress={() => void replaceMaster()} loading={upload.isPending} />}
            />
          ) : (
            <View style={{ gap: theme.space.md }}>
              <View style={styles.masterTop}>
                <View style={[styles.docIcon, { backgroundColor: colors.accentSoft, borderRadius: theme.radius.small }]}>
                  <Ionicons name="document-text" size={26} color={theme.accent} />
                </View>
                <View style={{ flex: 1, gap: 2 }}>
                  <T v="headline" numberOfLines={1}>
                    {m.filename}
                  </T>
                  <T v="footnote" color={colors.text2}>
                    Revision {m.revision} · updated {when(m.updated_at)}
                  </T>
                  <View style={styles.chips}>
                    {m.compile_error ? (
                      <Chip label="LaTeX error" tone="bad" icon="warning-outline" />
                    ) : m.has_pdf ? (
                      <Chip label={`Compiles · ${m.pages} page${m.pages === 1 ? "" : "s"}`} tone="good" icon="checkmark-circle" />
                    ) : (
                      <Chip label="Compiling…" icon="time-outline" />
                    )}
                  </View>
                </View>
              </View>
              {m.compile_error ? (
                <T v="caption" color={colors.danger} numberOfLines={8} selectable>
                  {m.compile_error}
                </T>
              ) : null}
              <View style={{ gap: 6 }}>
                {m.sections.map((section, index) => {
                  const entries = (section.entries as unknown[] | undefined) ?? [];
                  const detail =
                    section.kind === "entries"
                      ? `${entries.length} entr${entries.length === 1 ? "y" : "ies"}`
                      : section.kind === "skills"
                        ? "skills lines"
                        : section.kind === "list"
                          ? "bullets"
                          : section.kind === "summary"
                            ? "paragraph"
                            : "kept as written";
                  const tailored = TAILORED_ROLES.includes(String(section.role));
                  return (
                    <View key={index} style={styles.sectionRow}>
                      <Ionicons name={tailored ? "sparkles" : "lock-closed-outline"} size={13} color={tailored ? theme.accent : colors.text3} />
                      <T v="footnote" style={{ flex: 1 }}>
                        {String(section.title)}
                      </T>
                      <T v="footnote" color={colors.text2}>
                        {detail}
                      </T>
                    </View>
                  );
                })}
                <T v="caption" color={colors.text2}>
                  Sparkles mark the sections tailored for each job. Everything else stays exactly as you wrote it.
                </T>
              </View>
              <View style={styles.buttons}>
                <Button label="View PDF" variant="gray" size="medium" icon="eye-outline" onPress={viewMaster} loading={link.isPending} disabled={!m.has_pdf} style={{ flex: 1 }} />
                <Button label="Replace" variant="gray" size="medium" icon="swap-horizontal" onPress={() => void replaceMaster()} loading={upload.isPending} style={{ flex: 1 }} />
              </View>
              <Button label="Generate General Version" variant="tinted" size="medium" icon="sparkles" onPress={generateGeneral} loading={create.isPending} disabled={!m.has_pdf} />
              {upload.isError ? (
                <T v="footnote" color={colors.danger}>
                  {upload.error.message}
                </T>
              ) : null}
            </View>
          )}
        </Card>
      </View>

      <View style={{ gap: theme.space.md }}>
        <Segmented
          options={[
            { value: "all", label: "All" },
            { value: "RESUME", label: "Résumés" },
            { value: "COVER_LETTER", label: "Letters" },
            { value: "starred", label: "Starred" },
          ]}
          value={filter}
          onChange={setFilter}
        />
        {documents.isPending ? (
          <Loading />
        ) : shown.length === 0 ? (
          <EmptyState
            icon="documents-outline"
            title={all.length === 0 ? "No tailored documents yet" : "Nothing here"}
            message={all.length === 0 ? "Open a job and tap “Tailor résumé” or “Cover letter”. You'll get an alert when it's ready." : undefined}
          />
        ) : (
          <Group footer={`${all.length} document${all.length === 1 ? "" : "s"}, each built only from your verified profile.`}>
            {shown.map((doc) => (
              <DocumentRow key={doc.id} doc={doc} />
            ))}
          </Group>
        )}
      </View>
    </Screen>
  );
}

const styles = StyleSheet.create({
  masterTop: { flexDirection: "row", gap: 12, alignItems: "center" },
  docIcon: { width: 52, height: 52, alignItems: "center", justifyContent: "center" },
  sectionRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  chips: { flexDirection: "row", gap: 6, marginTop: 4 },
  buttons: { flexDirection: "row", gap: 8 },
});
