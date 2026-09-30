import { router } from "expo-router";
import { useState } from "react";
import { ActivityIndicator, Alert, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { OptionGroup } from "@/components/settings-kit";
import { Button, Card, EmptyState, Field, Group, IconButton, Loading, Row, Segmented, SwitchRow, T } from "@/components/ui";
import { type Schema, useSourceActions, useSources } from "@/lib/api";
import { useCatalog } from "@/lib/careers";
import { titleCase, useWhen } from "@/lib/format";
import { useTheme } from "@/lib/theme";

type Source = Schema<"SourceOut">;
type Cadence = Schema<"DiscoveryCadence">;
type BoardType = "GREENHOUSE" | "LEVER" | "ASHBY" | "SMARTRECRUITERS" | "CAREER_PAGE" | "RSS";

const BOARDS: { value: BoardType; label: string; key: string; placeholder: string; help: string }[] = [
  { value: "GREENHOUSE", label: "Greenhouse", key: "board_token", placeholder: "e.g. stripe", help: "The part after boards.greenhouse.io/" },
  { value: "LEVER", label: "Lever", key: "company", placeholder: "e.g. netflix", help: "The part after jobs.lever.co/" },
  { value: "ASHBY", label: "Ashby", key: "organization", placeholder: "e.g. linear", help: "The part after jobs.ashbyhq.com/" },
  { value: "SMARTRECRUITERS", label: "SmartRecruiters", key: "company", placeholder: "e.g. BoschGroup", help: "The company identifier in the careers URL" },
  { value: "CAREER_PAGE", label: "Career page", key: "url", placeholder: "https://company.com/careers", help: "Pages that publish schema.org job postings" },
  { value: "RSS", label: "RSS / Atom feed", key: "url", placeholder: "https://example.edu/jobs.rss", help: "Job feeds from boards, universities and labs" },
];

const CADENCES: { value: Cadence; label: string }[] = [
  { value: "HOURLY", label: "1h" },
  { value: "EVERY_6_HOURS", label: "6h" },
  { value: "DAILY", label: "Daily" },
  { value: "MANUAL", label: "Manual" },
];

const HEALTH_COLOR: Record<Source["health"], string> = {
  healthy: "#34C759",
  degraded: "#FF9500",
  failing: "#FF3B30",
  never_run: "#8E8E93",
  disabled: "#C7C7CC",
};

function SourceDetail({ source }: { source: Source }) {
  const theme = useTheme();
  const when = useWhen();
  const { run, update, remove } = useSourceActions();
  const running = run.isPending && run.variables === source.id;
  const cadenceOptions = CADENCES.some((c) => c.value === source.cadence)
    ? CADENCES
    : [...CADENCES, { value: source.cadence, label: titleCase(source.cadence) }];

  const confirmDelete = () =>
    Alert.alert(`Delete “${source.name}”?`, "Jobs already discovered stay in your inbox.", [
      { text: "Cancel", style: "cancel" },
      { text: "Delete", style: "destructive", onPress: () => remove.mutate(source.id) },
    ]);

  return (
    <Group
      header={source.name}
      footer={
        source.last_error && source.health !== "healthy"
          ? `Last error: ${source.last_error}`
          : source.last_run_at
            ? `Last checked ${when(source.last_run_at)} · ${source.last_jobs_found} found last time · ${source.total_jobs_found} total`
            : "Not checked yet."
      }
    >
      <Row
        title={titleCase(source.type)}
        subtitle={titleCase(source.health)}
        left={<View style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: HEALTH_COLOR[source.health] }} />}
        right={
          running ? (
            <ActivityIndicator color={theme.colors.text2} />
          ) : (
            <IconButton icon="play" label={`Check ${source.name} now`} tint={theme.accent} disabled={!source.enabled} onPress={() => run.mutate(source.id)} />
          )
        }
      />
      <SwitchRow title="Enabled" value={source.enabled} onChange={(enabled) => update.mutate({ id: source.id, patch: { enabled } })} />
      <Row
        title="Check"
        below={<Segmented options={cadenceOptions} value={source.cadence} onChange={(cadence) => update.mutate({ id: source.id, patch: { cadence } })} />}
      />
      <Row title="Delete Source" destructive onPress={confirmDelete} />
    </Group>
  );
}

function AddSource({ onDone }: { onDone: () => void }) {
  const theme = useTheme();
  const { create } = useSourceActions();
  const [type, setType] = useState<BoardType>("GREENHOUSE");
  const [value, setValue] = useState("");
  const [company, setCompany] = useState("");
  const board = BOARDS.find((option) => option.value === type) ?? BOARDS[0];

  const submit = () => {
    const token = value.trim();
    if (!token) return;
    const config: Record<string, string> = { [board.key]: token };
    if (company.trim()) config.company_name = company.trim();
    create.mutate(
      { name: company.trim() || token, type, config, cadence: "DAILY", enabled: true },
      {
        onSuccess: () => {
          theme.haptic("success");
          onDone();
        },
      },
    );
  };

  return (
    <>
      <OptionGroup header="New source" options={BOARDS.map(({ value: v, label, help }) => ({ value: v, label, subtitle: help }))} value={type} onChange={setType} />
      <Card>
        <View style={{ gap: theme.space.md }}>
          <Field
            label={board.key === "url" ? "URL" : "Board"}
            value={value}
            onChangeText={setValue}
            placeholder={board.placeholder}
            autoCapitalize="none"
            autoCorrect={false}
            keyboardType={board.key === "url" ? "url" : "default"}
          />
          <Field label="Company name (optional)" value={company} onChangeText={setCompany} placeholder="Shown on job cards" />
          {create.isError ? (
            <T v="footnote" color={theme.colors.danger}>
              {create.error.message}
            </T>
          ) : null}
          <View style={{ flexDirection: "row", gap: theme.space.sm }}>
            <Button label="Cancel" variant="gray" onPress={onDone} style={{ flex: 1 }} />
            <Button label="Add" onPress={submit} loading={create.isPending} disabled={!value.trim()} style={{ flex: 1 }} />
          </View>
          <T v="footnote" color={theme.colors.text2}>
            Checked daily through official job-board APIs and public feeds. CareerOS respects robots.txt and never logs in anywhere.
          </T>
        </View>
      </Card>
    </>
  );
}

export default function SourcesScreen() {
  const sources = useSources();
  const catalog = useCatalog(undefined, "");
  const [adding, setAdding] = useState(false);
  const refresh = useRefresh(() => sources.refetch());

  return (
    <Screen
      title="Job Sources"
      back="Settings"
      backFallback="/settings"
      tabBar={false}
      refresh={refresh}
      accessory={!adding ? <Button label="Add" icon="add" variant="tinted" size="small" onPress={() => setAdding(true)} /> : undefined}
    >
      <Group footer={`${catalog.data ? `${catalog.data.length} verified` : "Verified"} company boards for India and Australia (Greenhouse, Lever, Ashby, SmartRecruiters and Workday).`}>
        <Row title="Browse Companies" icon="business" iconColor="#5856D6" chevron onPress={() => router.push("/settings/catalog")} />
      </Group>
      {adding ? <AddSource onDone={() => setAdding(false)} /> : null}
      {sources.isPending ? (
        <Loading />
      ) : sources.isError ? (
        <Card>
          <EmptyState
            icon="cloud-offline-outline"
            title="Couldn't load sources"
            message={sources.error.message}
            action={<Button label="Try Again" variant="tinted" size="medium" onPress={() => void sources.refetch()} />}
          />
        </Card>
      ) : sources.data.length === 0 && !adding ? (
        <EmptyState
          icon="globe-outline"
          title="No sources yet"
          message="Add the Greenhouse, Lever or Ashby boards of companies you care about."
          action={<Button label="Add a Source" size="medium" onPress={() => setAdding(true)} />}
        />
      ) : (
        sources.data.map((source) => <SourceDetail key={source.id} source={source} />)
      )}
    </Screen>
  );
}
