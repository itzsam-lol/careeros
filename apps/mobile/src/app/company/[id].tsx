import { useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Alert, StyleSheet, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { Button, Card, Chip, EmptyState, Group, Loading, Row, SwitchRow, T } from "@/components/ui";
import { useOpenLink, useProfile, useUpdatePreferences } from "@/lib/api";
import { type CompanyInsights, useCompany } from "@/lib/careers";
import { isDreamCompany, toggleDreamCompany } from "@/lib/dream";
import { shortDate } from "@/lib/format";
import { openJob } from "@/lib/nav";
import { useTheme } from "@/lib/theme";

type Count = CompanyInsights["by_country"][number];

function ChipGroup({ header, items, footer }: { header: string; items: Count[]; footer?: string }) {
  const theme = useTheme();
  if (items.length === 0) return null;
  return (
    <View style={{ gap: 7 }}>
      <T v="footnote" color={theme.colors.text2} style={styles.header}>
        {header}
      </T>
      <Card>
        <View style={styles.chips}>
          {items.map((item) => (
            <Chip key={item.label} label={`${item.label} · ${item.count}`} />
          ))}
        </View>
      </Card>
      {footer ? (
        <T v="footnote" color={theme.colors.text2} style={{ paddingHorizontal: 16 }}>
          {footer}
        </T>
      ) : null}
    </View>
  );
}

/** Dream companies get a tailored application kit and an alert for every fresher role. */
function DreamCompanySwitch({ name }: { name: string }) {
  const profile = useProfile();
  const update = useUpdatePreferences();
  const [shown, setShown] = useState<boolean | null>(null);
  const saved = profile.data?.preferences.target_companies;
  if (!saved) return null;
  const on = shown ?? isDreamCompany(name, saved);
  const change = (next: boolean) => {
    setShown(next);
    update.mutate(
      { target_companies: toggleDreamCompany(name, saved, next) },
      {
        onSettled: () => setShown(null),
        onError: (error) => Alert.alert("Couldn't update dream companies", error.message),
      },
    );
  };
  return (
    <Group
      footer={
        on
          ? `Every fresher role at ${name} that you're eligible for gets a tailored résumé, a cover letter and a Ready to Apply alert.`
          : `Get a tailored application kit and an alert for every fresher role at ${name} that you're eligible for.`
      }
    >
      <SwitchRow title="Dream Company" icon="star" iconColor="#FF9500" value={on} disabled={update.isPending} onChange={change} />
    </Group>
  );
}

/** What CareerOS knows about the company behind a job, plus people and research links. */
export default function CompanyScreen() {
  const theme = useTheme();
  const { colors } = theme;
  const { id } = useLocalSearchParams<{ id: string }>();
  const company = useCompany(id);
  const openLink = useOpenLink();
  const refresh = useRefresh(() => company.refetch());
  const data = company.data;

  return (
    <Screen
      back="Job"
      tabBar={false}
      refresh={refresh}
      title={data?.name ?? "Company"}
      subtitle={data ? `${data.open_roles} open role${data.open_roles === 1 ? "" : "s"} tracked · ${data.entry_level_roles} entry-level` : undefined}
    >
      {company.isPending ? (
        <Loading />
      ) : company.isError || !data ? (
        <EmptyState icon="business-outline" title="Couldn't load the company" message={company.error?.message} />
      ) : (
        <>
          <DreamCompanySwitch name={data.name} />
          {data.summary ? (
            <Group header="About" footer={data.summary_source ? "Summary from Wikipedia." : undefined}>
              <View style={{ padding: theme.space.lg, gap: 8 }}>
                <T v="body">{data.summary}</T>
                {data.summary_source ? (
                  <View style={{ alignSelf: "flex-start" }}>
                    <Button label="Read More" variant="plain" size="small" onPress={() => openLink(data.summary_source as string)} />
                  </View>
                ) : null}
              </View>
            </Group>
          ) : null}

          {data.your_matches.length > 0 ? (
            <Group header="Your matches here">
              {data.your_matches.map((match) => (
                <Row
                  key={match.job_id}
                  title={match.title}
                  subtitle={[match.location, `${Math.round(match.score * 100)}% match`].filter(Boolean).join(" · ")}
                  numberOfLines={2}
                  chevron
                  onPress={() => openJob(match.job_id, data.name)}
                />
              ))}
            </Group>
          ) : null}

          <View style={[styles.stats, { gap: theme.space.sm }]}>
            {(
              [
                ["Open roles", data.open_roles],
                ["Entry-level", data.entry_level_roles],
                ["Visa offered (AU)", data.sponsorship_roles],
              ] as const
            ).map(([label, value]) => (
              <Card key={label} style={{ flex: 1, padding: theme.space.md }}>
                <T v="title2" style={{ fontVariant: ["tabular-nums"] }}>
                  {value}
                </T>
                <T v="caption" color={colors.text2} fit>
                  {label}
                </T>
              </Card>
            ))}
          </View>

          <ChipGroup header="Where they're hiring" items={data.by_country} />
          <ChipGroup header="Cities" items={data.top_cities} />
          <ChipGroup header="Levels" items={data.by_level} />
          <ChipGroup header="Kinds of work" items={data.by_function} />
          <ChipGroup
            header="Skills they ask for most"
            items={data.top_skills}
            footer={data.newest_posting ? `Newest posting ${shortDate(data.newest_posting)}. Counts cover the roles CareerOS has found.` : undefined}
          />

          <Group header="People to contact" footer="Opens a LinkedIn search. Reach out with one of the message drafts on the job page.">
            {data.people_searches.map((link) => (
              <Row key={link.label} title={link.label} icon="people" iconColor="#0A66C2" chevron onPress={() => openLink(link.url)} />
            ))}
          </Group>

          <Group header="Research">
            {data.research_links.map((link) => (
              <Row key={link.label} title={link.label} icon="search" iconColor="#8E8E93" chevron onPress={() => openLink(link.url)} />
            ))}
          </Group>
        </>
      )}
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { paddingHorizontal: 16, textTransform: "uppercase" },
  chips: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  stats: { flexDirection: "row" },
});
