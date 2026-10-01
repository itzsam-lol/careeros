import * as Clipboard from "expo-clipboard";
import { useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Alert, Share, TextInput, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { Button, Card, Chip, EmptyState, Group, Loading, Row, T } from "@/components/ui";
import { useJob } from "@/lib/api";
import { type Draft, useOutreach } from "@/lib/careers";
import { EMAIL_KINDS, type EmailKind, emailStatus, useCreateEmail, useEmails } from "@/lib/email";
import { useWhen } from "@/lib/format";
import { openEmail } from "@/lib/nav";
import { useTheme } from "@/lib/theme";

function DraftCard({ draft, jobId }: { draft: Draft; jobId: string }) {
  const theme = useTheme();
  const { colors } = theme;
  const [text, setText] = useState(draft.body);
  const [copied, setCopied] = useState(false);
  const create = useCreateEmail();
  const limit = draft.kind === "connection_note" ? 300 : null;
  const emailable = EMAIL_KINDS.includes(draft.kind);
  const startEmail = () =>
    create.mutate(
      {
        job_id: jobId,
        kind: draft.kind as EmailKind,
        to_address: "",
        subject: draft.subject || draft.title,
        body: text,
        attach_resume: draft.kind === "referral_request",
      },
      {
        onSuccess: (email) => openEmail(email.id, "Messages"),
        onError: (error) => Alert.alert("Couldn't start the email", error.message),
      },
    );
  return (
    <View style={{ gap: 7 }}>
      <T v="footnote" color={colors.text2} style={{ paddingHorizontal: 16, textTransform: "uppercase" }}>
        {draft.title}
      </T>
      <Card>
        <View style={{ gap: theme.space.md }}>
          {draft.subject ? (
            <T v="subhead" color={colors.text2}>
              Subject: <T v="subhead">{draft.subject}</T>
            </T>
          ) : null}
          <TextInput
            multiline
            value={text}
            onChangeText={setText}
            accessibilityLabel={`${draft.title} text`}
            selectionColor={theme.accent}
            style={[theme.type.callout, { color: colors.text, backgroundColor: colors.fill, borderRadius: theme.radius.small, padding: 12, minHeight: limit ? 110 : 220, textAlignVertical: "top" }]}
          />
          {limit ? (
            <T v="caption" color={text.length > limit ? colors.danger : colors.text2}>
              {text.length}/{limit} characters (LinkedIn's limit for connection notes)
            </T>
          ) : null}
          <View style={{ flexDirection: "row", gap: 8 }}>
            <Button
              label={copied ? "Copied" : "Copy"}
              variant="gray"
              size="medium"
              icon={copied ? "checkmark" : "copy-outline"}
              onPress={() =>
                void Clipboard.setStringAsync(draft.subject ? `${draft.subject}\n\n${text}` : text).then(() => {
                  theme.haptic("success");
                  setCopied(true);
                  setTimeout(() => setCopied(false), 1500);
                })
              }
              style={{ flex: 1 }}
            />
            <Button
              label="Share"
              variant="gray"
              size="medium"
              icon="share-outline"
              onPress={() => void Share.share({ message: text, title: draft.subject || draft.title })}
              style={{ flex: 1 }}
            />
          </View>
          {emailable ? (
            <Button
              label={create.isPending ? "Opening…" : "Email This"}
              variant="tinted"
              size="medium"
              icon="mail"
              disabled={create.isPending}
              onPress={startEmail}
            />
          ) : null}
        </View>
      </Card>
    </View>
  );
}

export default function OutreachScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const job = useJob(id);
  const drafts = useOutreach(id);
  const emails = useEmails(id);
  const when = useWhen();
  const refresh = useRefresh(() => Promise.all([drafts.refetch(), emails.refetch()]));
  return (
    <Screen
      back="Job"
      tabBar={false}
      refresh={refresh}
      title="Messages"
      subtitle={job.data ? `Drafts for ${job.data.card.company}. Edit, copy or share; nothing is sent automatically.` : undefined}
    >
      {emails.data && emails.data.length > 0 ? (
        <Group header="Your emails for this job">
          {emails.data.map((email) => {
            const status = emailStatus(email);
            return (
              <Row
                key={email.id}
                title={email.subject}
                subtitle={[email.to_name || email.to_address || "No recipient yet", when(email.sent_at ?? email.updated_at)].join(" · ")}
                numberOfLines={2}
                right={<Chip label={status.label} tone={status.tone} />}
                chevron
                onPress={() => openEmail(email.id, "Messages")}
              />
            );
          })}
        </Group>
      ) : null}
      {drafts.isPending ? (
        <Loading />
      ) : drafts.isError ? (
        <EmptyState icon="alert-circle-outline" title="Couldn't draft messages" message={drafts.error.message} />
      ) : (
        drafts.data.map((draft) => <DraftCard key={draft.kind} draft={draft} jobId={id} />)
      )}
    </Screen>
  );
}
