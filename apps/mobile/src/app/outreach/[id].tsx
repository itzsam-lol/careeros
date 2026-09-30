import * as Clipboard from "expo-clipboard";
import { useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Share, TextInput, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { Button, Card, EmptyState, Loading, T } from "@/components/ui";
import { useJob } from "@/lib/api";
import { type Draft, useOutreach } from "@/lib/careers";
import { useTheme } from "@/lib/theme";

function DraftCard({ draft }: { draft: Draft }) {
  const theme = useTheme();
  const { colors } = theme;
  const [text, setText] = useState(draft.body);
  const [copied, setCopied] = useState(false);
  const limit = draft.kind === "connection_note" ? 300 : null;
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
              variant="tinted"
              size="medium"
              icon="share-outline"
              onPress={() => void Share.share({ message: text, title: draft.subject || draft.title })}
              style={{ flex: 1 }}
            />
          </View>
        </View>
      </Card>
    </View>
  );
}

export default function OutreachScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const job = useJob(id);
  const drafts = useOutreach(id);
  const refresh = useRefresh(() => drafts.refetch());
  return (
    <Screen
      back="Job"
      tabBar={false}
      refresh={refresh}
      title="Messages"
      subtitle={job.data ? `Drafts for ${job.data.card.company}. Edit, copy or share; nothing is sent automatically.` : undefined}
    >
      {drafts.isPending ? (
        <Loading />
      ) : drafts.isError ? (
        <EmptyState icon="alert-circle-outline" title="Couldn't draft messages" message={drafts.error.message} />
      ) : (
        drafts.data.map((draft) => <DraftCard key={draft.kind} draft={draft} />)
      )}
    </Screen>
  );
}
