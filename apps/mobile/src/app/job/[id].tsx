import Ionicons from "@expo/vector-icons/Ionicons";
import { router, useLocalSearchParams } from "expo-router";
import { useState } from "react";
import { Alert, Pressable, StyleSheet, View } from "react-native";

import { ApplicationCard, JobDocuments } from "@/components/job-actions";
import { locationLine, matchTone } from "@/components/job-card";
import { Screen, useRefresh } from "@/components/screen";
import { Bar, Button, Card, Chip, EmptyState, Group, type IconName, Loading, Row, Score, T } from "@/components/ui";
import { type JobDetail, useJob, useJobAction, useOpenLink, useRematch } from "@/lib/api";
import { salaryText, shortDate, titleCase, useWhen } from "@/lib/format";
import { useTheme } from "@/lib/theme";

type Match = NonNullable<JobDetail["match"]>;
type Analysis = NonNullable<JobDetail["analysis"]>;

const DIMENSIONS: [string, string][] = [
  ["skills", "Skills"],
  ["projects", "Projects"],
  ["experience", "Experience"],
  ["research", "Research"],
  ["domain", "Domain"],
  ["preferences", "Your preferences"],
];

function Section({ title, children, footer }: { title: string; children: React.ReactNode; footer?: string }) {
  const theme = useTheme();
  return (
    <View style={{ gap: 7 }}>
      <T v="footnote" color={theme.colors.text2} style={{ paddingHorizontal: 16, textTransform: "uppercase" }}>
        {title}
      </T>
      <Card>
        <View style={{ gap: theme.space.md }}>{children}</View>
      </Card>
      {footer ? (
        <T v="footnote" color={theme.colors.text2} style={{ paddingHorizontal: 16 }}>
          {footer}
        </T>
      ) : null}
    </View>
  );
}

function Bullet({ icon, color, children }: { icon: IconName; color: string; children: React.ReactNode }) {
  return (
    <View style={styles.bullet}>
      <Ionicons name={icon} size={19} color={color} style={{ marginTop: 1 }} />
      <T v="callout" style={{ flex: 1 }}>
        {children}
      </T>
    </View>
  );
}

function WhyItMatches({ match }: { match: Match }) {
  const theme = useTheme();
  return (
    <Section title="Why it matches">
      <T v="body">{match.reasoning}</T>
      {match.strengths.map((strength, index) => {
        const evidence = Array.isArray(strength.evidence) ? (strength.evidence as { ref: string; title: string }[]) : [];
        return (
          <View key={index} style={{ gap: 6 }}>
            <Bullet icon="checkmark-circle" color={theme.colors.success}>
              {String(strength.text)}
            </Bullet>
            {evidence.length > 0 ? (
              <View style={[styles.wrap, { paddingLeft: 27 }]}>
                {evidence.map((ref) => (
                  <Chip key={ref.ref} label={ref.title} tone="accent" icon="document-text-outline" />
                ))}
              </View>
            ) : null}
          </View>
        );
      })}
    </Section>
  );
}

function GapsAndConcerns({ match }: { match: Match }) {
  const theme = useTheme();
  if (match.gaps.length === 0 && match.concerns.length === 0) return null;
  return (
    <Section title="Gaps & concerns">
      {match.gaps.map((gap, index) => (
        <Bullet key={`g${index}`} icon="remove-circle" color={theme.colors.danger}>
          {String(gap.text)}
        </Bullet>
      ))}
      {match.concerns.map((concern, index) => (
        <Bullet key={`c${index}`} icon="alert-circle" color={theme.colors.warning}>
          {concern}
        </Bullet>
      ))}
    </Section>
  );
}

function Coverage({ match }: { match: Match }) {
  const theme = useTheme();
  const rows = match.requirement_coverage as { skill: string; required: boolean; status: string }[];
  if (rows.length === 0) return null;
  const tone = (status: string) => (status === "MATCHED" ? "good" : status === "PARTIAL" ? "warn" : "neutral") as "good" | "warn" | "neutral";
  return (
    <Section title="Skills the role asks for" footer="Green: backed by verified evidence · Orange: partial or unverified · Gray: not in your profile">
      {[true, false].map((required) => {
        const group = rows.filter((row) => row.required === required);
        if (group.length === 0) return null;
        return (
          <View key={String(required)} style={{ gap: 8 }}>
            <T v="subhead" color={theme.colors.text2}>
              {required ? "Required" : "Preferred"}
            </T>
            <View style={styles.wrap}>
              {group.map((row) => (
                <Chip key={row.skill} label={row.skill} tone={tone(row.status)} />
              ))}
            </View>
          </View>
        );
      })}
    </Section>
  );
}

function Eligibility({ match }: { match: Match }) {
  const theme = useTheme();
  if (match.eligibility.length === 0) return null;
  const icon: Record<string, [IconName, string]> = {
    PASS: ["checkmark-circle", theme.colors.success],
    FAIL: ["close-circle", theme.colors.danger],
  };
  return (
    <Section title="Eligibility">
      {match.eligibility.map((check) => {
        const [name, color] = icon[check.status] ?? ["help-circle", theme.colors.warning];
        return (
          <Bullet key={`${check.key}-${check.detail}`} icon={name} color={color}>
            <T v="callout" style={theme.type.headline}>
              {check.label}:{" "}
            </T>
            {check.detail}
          </Bullet>
        );
      })}
    </Section>
  );
}

function Breakdown({ match }: { match: Match }) {
  const theme = useTheme();
  return (
    <Section title="Match breakdown" footer="Relevance to your verified profile, not a prediction of hiring chances.">
      {DIMENSIONS.map(([key, label]) => {
        const value = match.dimensions[key] ?? 0;
        return (
          <View key={key} style={{ gap: 6 }}>
            <View style={styles.between}>
              <T v="subhead">{label}</T>
              <T v="subhead" color={theme.colors.text2} style={{ fontVariant: ["tabular-nums"] }}>
                {Math.round(value * 100)}
              </T>
            </View>
            <Bar value={value} />
          </View>
        );
      })}
    </Section>
  );
}

function AtAGlance({ analysis, detail }: { analysis: Analysis; detail: JobDetail }) {
  const rows: [string, string | null][] = [
    ["Seniority", analysis.seniority !== "UNKNOWN" ? titleCase(analysis.seniority) : null],
    ["Domain", analysis.domain !== "OTHER" ? titleCase(analysis.domain).replace("Ml Ai", "ML / AI") : null],
    ["Experience", analysis.min_years_experience ? `${analysis.min_years_experience}+ years` : null],
    ["Student role", analysis.requires_current_student ? "Current students" : null],
    ["Graduating", analysis.graduation_years?.length ? analysis.graduation_years.join(", ") : null],
    ["Visa sponsorship", analysis.sponsorship === "UNKNOWN" ? "Not stated" : titleCase(analysis.sponsorship)],
    ["Compensation", salaryText(detail.card.salary)],
    ["Department", detail.department],
    ["Apply via", titleCase(detail.card.application_platform)],
  ];
  return (
    <Group header="Role at a glance">
      {rows
        .filter(([, value]) => value)
        .map(([label, value]) => (
          <Row key={label} title={label} value={value} />
        ))}
    </Group>
  );
}

export default function JobDetailScreen() {
  const theme = useTheme();
  const { colors, prefs } = theme;
  const { id, from } = useLocalSearchParams<{ id: string; from?: string }>();
  const job = useJob(id);
  const action = useJobAction(id);
  const rematch = useRematch(id);
  const openLink = useOpenLink();
  const when = useWhen();
  const refresh = useRefresh(() => job.refetch());
  const [expanded, setExpanded] = useState(prefs.expandDescription);

  if (job.isPending || job.isError) {
    return (
      <Screen back={from ?? "Jobs"} backFallback="/jobs" tabBar={false} refresh={refresh}>
        {job.isPending ? (
          <Loading />
        ) : (
          <Card>
            <EmptyState
              icon="cloud-offline-outline"
              title="Couldn't load this job"
              message={job.error.message}
              action={<Button label="Try Again" variant="tinted" size="medium" onPress={() => void job.refetch()} />}
            />
          </Card>
        )}
      </Screen>
    );
  }

  const detail = job.data;
  const { card, match, analysis } = detail;
  const saved = card.status === "SAVED";
  const dismissed = card.status === "DISMISSED";
  const act = (kind: "save" | "dismiss" | "restore") => {
    theme.haptic("light");
    action.mutate(kind);
  };
  const dismiss = () => {
    if (!prefs.confirmDismiss) return act("dismiss");
    Alert.alert("Dismiss this role?", "It moves to Dismissed and stops appearing in your inbox. You can restore it any time.", [
      { text: "Cancel", style: "cancel" },
      { text: "Dismiss", style: "destructive", onPress: () => act("dismiss") },
    ]);
  };
  const meta = [
    `Found ${when(card.first_seen_at)}`,
    card.posted_at ? `posted ${when(card.posted_at)}` : null,
    card.deadline ? `closes ${shortDate(card.deadline)}` : null,
  ].filter(Boolean);

  return (
    <Screen back={from ?? "Jobs"} backFallback="/jobs" tabBar={false} refresh={refresh}>
      <View style={{ gap: theme.space.md }}>
        <View style={styles.header}>
          <View style={{ flex: 1, gap: 4 }}>
            <T v="title1">{card.title}</T>
            <T v="callout" color={colors.text2}>
              {locationLine(card)}
            </T>
          </View>
          {match && prefs.scoreStyle !== "hidden" ? <Score score={match.overall_score} eligible={match.eligible} size={72} style="ring" /> : null}
        </View>
        <View style={styles.wrap}>
          {match ? <Chip label={match.label} tone={matchTone(match.label, match.eligible)} /> : <Chip label="Analysing" />}
          {!card.is_active ? <Chip label="Closed" tone="bad" /> : null}
          {saved ? <Chip label="Saved" tone="accent" icon="bookmark" /> : null}
          {dismissed ? <Chip label="Dismissed" /> : null}
        </View>
        <T v="footnote" color={colors.text2}>
          {meta.join(" · ")}
          {match?.stale ? " · match updating after your profile changed" : ""}
        </T>
      </View>

      <View style={{ gap: theme.space.sm }}>
        {card.application_url ? <Button label="View Posting" icon="open-outline" onPress={() => openLink(card.application_url ?? "")} /> : null}
        <View style={{ flexDirection: "row", gap: theme.space.sm }}>
          <Button
            label={saved ? "Saved" : "Save"}
            icon={saved ? "bookmark" : "bookmark-outline"}
            variant="tinted"
            onPress={() => act(saved ? "restore" : "save")}
            disabled={action.isPending}
            style={{ flex: 1 }}
          />
          {dismissed ? (
            <Button label="Restore" icon="arrow-undo" variant="gray" onPress={() => act("restore")} disabled={action.isPending} style={{ flex: 1 }} />
          ) : (
            <Button label="Dismiss" icon="close" variant="gray" onPress={dismiss} disabled={action.isPending} style={{ flex: 1 }} />
          )}
        </View>
        {action.isError ? (
          <T v="footnote" color={colors.danger}>
            {action.error.message}
          </T>
        ) : null}
      </View>

      {analysis?.injection_detected ? (
        <View style={[styles.notice, { backgroundColor: colors.warningSoft, borderRadius: theme.radius.card }]}>
          <Ionicons name="shield-half" size={20} color={colors.warning} />
          <T v="subhead" style={{ flex: 1 }}>
            This posting contains text addressed to AI assistants (for example, instructions to rate candidates). CareerOS ignored it when analysing the role.
          </T>
        </View>
      ) : null}

      <Group>
        <Row
          title="Apply Kit"
          subtitle="Documents, copy-ready answers and a short pitch for this job"
          icon="paper-plane"
          iconColor="#34C759"
          numberOfLines={2}
          chevron
          onPress={() => router.push({ pathname: "/apply/[id]", params: { id } })}
        />
      </Group>
      <ApplicationCard jobId={id} />
      <JobDocuments jobId={id} />
      <Group header="Company">
        <Row
          title={`About ${card.company}`}
          subtitle="Open roles, skills they ask for, people to contact"
          icon="business"
          iconColor="#FF9500"
          numberOfLines={2}
          chevron
          onPress={() => router.push({ pathname: "/company/[id]", params: { id } })}
        />
      </Group>

      {match ? (
        <>
          <WhyItMatches match={match} />
          <GapsAndConcerns match={match} />
          <Coverage match={match} />
          <Eligibility match={match} />
          <Breakdown match={match} />
        </>
      ) : (
        <Section title="Match">
          <T v="body" color={colors.text2}>
            The agent is still analysing this role. Pull down to refresh in a minute.
          </T>
        </Section>
      )}

      {analysis ? <AtAGlance analysis={analysis} detail={detail} /> : null}

      {analysis && (analysis.responsibilities ?? []).length > 0 ? (
        <Section title="What you'd do">
          {(analysis.responsibilities ?? []).slice(0, 6).map((item) => (
            <Bullet key={item} icon="ellipse" color={colors.text3}>
              {item}
            </Bullet>
          ))}
        </Section>
      ) : null}

      <Section title="Description">
        <T v="callout" numberOfLines={expanded ? undefined : 10} selectable>
          {detail.description || "No description provided."}
        </T>
        {detail.description && detail.description.length > 500 ? (
          <Pressable accessibilityRole="button" onPress={() => setExpanded((value) => !value)} hitSlop={8}>
            <T v="body" color={theme.accent}>
              {expanded ? "Show Less" : "Show More"}
            </T>
          </Pressable>
        ) : null}
      </Section>

      {detail.sources.length > 0 ? (
        <Group header="Seen on">
          {detail.sources.map((source, index) => (
            <Row
              key={index}
              title={source.source_name ?? titleCase(source.source_type)}
              subtitle={`Last seen ${when(source.last_seen_at)}`}
              chevron={!!source.url}
              onPress={source.url ? () => openLink(source.url ?? "") : undefined}
            />
          ))}
        </Group>
      ) : null}

      <Group footer="Re-scores this role against your current profile.">
        <Row
          title={rematch.isSuccess ? "Re-matching queued" : "Re-run Matching"}
          icon="refresh"
          iconColor="#8E8E93"
          onPress={() => rematch.mutate()}
          disabled={rematch.isPending}
        />
      </Group>
    </Screen>
  );
}

const styles = StyleSheet.create({
  header: { flexDirection: "row", gap: 16, alignItems: "flex-start" },
  bullet: { flexDirection: "row", gap: 8, alignItems: "flex-start" },
  wrap: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  between: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  notice: { flexDirection: "row", gap: 10, padding: 14 },
});
