import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Alert, Linking, StyleSheet, TextInput, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { Button, Card, Chip, EmptyState, Field, Group, Loading, Row, SwitchRow, T } from "@/components/ui";
import { emailStatus, type OutreachEmail, useCheckReplies, useEmail, useEmailAccount, useEmailActions } from "@/lib/email";
import { shortDate, useWhen } from "@/lib/format";
import { useTheme } from "@/lib/theme";

type Draft = Pick<OutreachEmail, "to_address" | "subject" | "body" | "attach_resume"> & { to_name: string };

const KIND_TITLES: Record<string, string> = {
  referral_request: "Referral Request",
  follow_up: "Follow-up",
  thank_you: "Thank-you Note",
  custom: "Email",
};

function SentView({ email }: { email: OutreachEmail }) {
  const theme = useTheme();
  const { colors } = theme;
  const when = useWhen();
  const check = useCheckReplies();
  const status = emailStatus(email);
  return (
    <>
      <Group>
        <Row title="To" value={email.to_name ? `${email.to_name}` : email.to_address} subtitle={email.to_name ? email.to_address : undefined} />
        <Row title="Sent" value={email.sent_at ? shortDate(email.sent_at) : "—"} right={<Chip label={status.label} tone={status.tone} />} />
        {email.attachment_name ? <Row title="Attachment" subtitle={email.attachment_name} icon="document-attach" iconColor="#0A84FF" /> : null}
      </Group>

      {email.reply_received_at ? (
        <Group header="Reply" footer="Read and answer it in Gmail.">
          <View style={{ padding: theme.space.lg, gap: 8 }}>
            <T v="headline">{email.reply_from ?? "Reply"}</T>
            <T v="caption" color={colors.text2}>
              {when(email.reply_received_at)}
            </T>
            <T v="body" selectable>
              {email.reply_snippet || "Open Gmail to read the reply."}
            </T>
            <View style={{ alignSelf: "flex-start" }}>
              <Button label="Open Gmail" variant="tinted" size="small" icon="mail-open" onPress={() => void Linking.openURL("https://mail.google.com/mail/u/0/#inbox")} />
            </View>
          </View>
        </Group>
      ) : email.status === "SENT" ? (
        <Group footer="Replies are checked every 10 minutes; you'll get a notification when one arrives.">
          <Row
            title={check.isPending ? "Checking…" : "Check for a reply now"}
            icon="refresh"
            iconColor="#34C759"
            onPress={() =>
              check.mutate(undefined, {
                onSuccess: (result) => Alert.alert(result.replies > 0 ? "New reply" : "No reply yet", result.replies > 0 ? "It's shown above." : "We'll keep checking."),
                onError: (error) => Alert.alert("Couldn't check", error.message),
              })
            }
          />
        </Group>
      ) : null}

      <View style={{ gap: 7 }}>
        <T v="footnote" color={colors.text2} style={styles.header}>
          {email.subject}
        </T>
        <Card>
          <T v="callout" selectable>
            {email.body}
          </T>
        </Card>
      </View>
    </>
  );
}

/** Edit a draft, then review and send it from the user's own Gmail. */
export default function EmailScreen() {
  const theme = useTheme();
  const { colors } = theme;
  const { id, from } = useLocalSearchParams<{ id: string; from?: string }>();
  const email = useEmail(id);
  const account = useEmailAccount();
  const { save, send, remove } = useEmailActions(id);
  const refresh = useRefresh(() => Promise.all([email.refetch(), account.refetch()]));
  // Unsaved edits; until the first one, the form shows the saved email.
  const [edits, setDraft] = useState<Draft | null>(null);
  const draft: Draft | null =
    edits ??
    (email.data
      ? {
          to_name: email.data.to_name ?? "",
          to_address: email.data.to_address,
          subject: email.data.subject,
          body: email.data.body,
          attach_resume: email.data.attach_resume,
        }
      : null);

  const data = email.data;
  const editable = data && (data.status === "DRAFT" || data.status === "FAILED");
  const connected = account.data?.connected ?? false;

  const changed = () =>
    !!draft &&
    !!data &&
    (draft.to_name !== (data.to_name ?? "") ||
      draft.to_address !== data.to_address ||
      draft.subject !== data.subject ||
      draft.body !== data.body ||
      draft.attach_resume !== data.attach_resume);

  const reviewAndSend = async () => {
    if (!draft || !data) return;
    try {
      if (changed()) await save.mutateAsync({ ...draft, to_name: draft.to_name || null });
    } catch (error) {
      Alert.alert("Couldn't save", (error as Error).message);
      return;
    }
    const to = draft.to_name ? `${draft.to_name} <${draft.to_address}>` : draft.to_address;
    Alert.alert(
      "Send this email?",
      `To: ${to}\nSubject: ${draft.subject}${draft.attach_resume ? "\nAttachment: your tailored résumé" : ""}\n\nIt goes out from ${account.data?.address ?? "your Gmail"} right away.`,
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Send",
          onPress: () =>
            send.mutate(undefined, {
              onSuccess: () => {
                theme.haptic("success");
                Alert.alert("Sent", "You'll get a notification if they reply.");
              },
              onError: (error) => Alert.alert("Not sent", error.message),
            }),
        },
      ],
    );
  };

  const confirmDelete = () =>
    Alert.alert("Delete this draft?", undefined, [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => remove.mutate(undefined, { onSuccess: () => router.back() }) },
    ]);

  return (
    <Screen
      back={from ?? "Back"}
      tabBar={false}
      refresh={refresh}
      title={data ? KIND_TITLES[data.kind] ?? "Email" : "Email"}
      subtitle={data?.job_title ? `${data.job_title} at ${data.company}` : undefined}
    >
      {email.isPending || (editable && draft === null) ? (
        <Loading />
      ) : email.isError || !data ? (
        <EmptyState icon="mail-unread-outline" title="Couldn't load this email" message={email.error?.message} />
      ) : !editable || !draft ? (
        <SentView email={data} />
      ) : (
        <>
          {!connected ? (
            <Card>
              <View style={{ gap: 10 }}>
                <T v="subhead">Connect your Gmail to send this. Drafts are saved either way.</T>
                <View style={{ alignSelf: "flex-start" }}>
                  <Button label="Connect Gmail" variant="tinted" size="small" icon="mail" onPress={() => router.push("/settings/email")} />
                </View>
              </View>
            </Card>
          ) : null}
          {data.status === "FAILED" && data.error ? (
            <Card>
              <T v="subhead" color={colors.danger}>
                Not sent: {data.error}
              </T>
            </Card>
          ) : null}

          <Group header="To">
            <View style={{ padding: theme.space.lg, gap: theme.space.md }}>
              <Field label="Name" value={draft.to_name} onChangeText={(to_name) => setDraft({ ...draft, to_name })} placeholder="e.g. Asha Rao" />
              <Field
                label="Email address"
                value={draft.to_address}
                onChangeText={(to_address) => setDraft({ ...draft, to_address: to_address.trim() })}
                autoCapitalize="none"
                autoCorrect={false}
                keyboardType="email-address"
                placeholder="name@company.com"
              />
            </View>
          </Group>

          <Group header="Message">
            <View style={{ padding: theme.space.lg, gap: theme.space.md }}>
              <Field label="Subject" value={draft.subject} onChangeText={(subject) => setDraft({ ...draft, subject })} />
              <TextInput
                multiline
                value={draft.body}
                onChangeText={(body) => setDraft({ ...draft, body })}
                accessibilityLabel="Email body"
                selectionColor={theme.accent}
                style={[theme.type.callout, { color: colors.text, backgroundColor: colors.fill, borderRadius: theme.radius.small, padding: 12, minHeight: 260, textAlignVertical: "top" }]}
              />
            </View>
          </Group>

          {data.job_id ? (
            <Group footer="Attaches the latest résumé tailored for this job.">
              <SwitchRow title="Attach tailored résumé" value={draft.attach_resume} onChange={(attach_resume) => setDraft({ ...draft, attach_resume })} />
            </Group>
          ) : null}

          <View style={{ gap: theme.space.sm }}>
            <Button
              label={send.isPending ? "Sending…" : "Review & Send"}
              icon="paper-plane"
              disabled={!connected || send.isPending || save.isPending || !draft.to_address || !draft.subject.trim() || !draft.body.trim()}
              onPress={() => void reviewAndSend()}
            />
            <Button
              label={save.isPending ? "Saving…" : "Save Draft"}
              variant="gray"
              disabled={!changed() || save.isPending}
              onPress={() =>
                save.mutate({ ...draft, to_name: draft.to_name || null }, { onError: (error) => Alert.alert("Couldn't save", error.message) })
              }
            />
            <Button label="Delete Draft" variant="plain" onPress={confirmDelete} />
          </View>
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: 16 },
});
