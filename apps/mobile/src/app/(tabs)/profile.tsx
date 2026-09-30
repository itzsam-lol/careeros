import Ionicons from "@expo/vector-icons/Ionicons";
import { ActivityIndicator, Alert, StyleSheet, View } from "react-native";

import { Screen, useRefresh } from "@/components/screen";
import { Bar, Button, Card, Chip, EmptyState, Group, IconButton, Loading, Row, T } from "@/components/ui";
import { type Schema, useProfile, useVerify } from "@/lib/api";
import { titleCase } from "@/lib/format";
import { useTheme } from "@/lib/theme";

type Profile = Schema<"ProfileOut">;
type Status = Schema<"VerificationStatus">;
type SectionKey = "experience" | "projects" | "education" | "research" | "publications" | "skills" | "achievements" | "facts" | "answers";

interface Item {
  section: SectionKey;
  id: string;
  title: string;
  subtitle: string | null;
  status: Status;
}

const SECTION_LABELS: Record<SectionKey, string> = {
  experience: "Experience",
  projects: "Project",
  education: "Education",
  research: "Research",
  publications: "Publication",
  skills: "Skill",
  achievements: "Achievement",
  facts: "Career fact",
  answers: "Saved answer",
};

const CATEGORY_LABELS: Record<string, string> = {
  PROGRAMMING_LANGUAGE: "Programming language",
  ML_AI: "ML / AI",
  DEVOPS: "DevOps",
  SOFT: "Soft skill",
  SPOKEN_LANGUAGE: "Spoken language",
};

function category(value: string): string {
  return CATEGORY_LABELS[value] ?? titleCase(value);
}

function monthYear(value: string | null): string {
  if (!value) return "";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleDateString(undefined, { month: "short", year: "numeric" });
}

function span(start: string | null, end: string | null, current: boolean): string {
  return [monthYear(start), current ? "Present" : monthYear(end)].filter(Boolean).join(" – ");
}

function flatten(profile: Profile): Item[] {
  const join = (...parts: (string | null | undefined)[]) => parts.filter(Boolean).join(" · ") || null;
  return [
    ...profile.experience.map((x) => ({ section: "experience" as const, id: x.id, title: x.role, subtitle: join(x.organization, span(x.start_date, x.end_date, x.is_current)), status: x.verification_status })),
    ...profile.projects.map((x) => ({ section: "projects" as const, id: x.id, title: x.name, subtitle: join(x.role, x.technologies.slice(0, 4).join(", ")), status: x.verification_status })),
    ...profile.education.map((x) => ({ section: "education" as const, id: x.id, title: x.field ? `${x.degree}, ${x.field}` : x.degree, subtitle: join(x.institution, span(x.start_date, x.end_date, x.is_current)), status: x.verification_status })),
    ...profile.research.map((x) => ({ section: "research" as const, id: x.id, title: x.title, subtitle: join(x.organization, span(x.start_date, x.end_date, x.is_current)), status: x.verification_status })),
    ...profile.publications.map((x) => ({ section: "publications" as const, id: x.id, title: x.title, subtitle: join(x.venue, x.year ? String(x.year) : null), status: x.verification_status })),
    ...profile.skills.map((x) => ({ section: "skills" as const, id: x.id, title: x.name, subtitle: category(x.category), status: x.verification_status })),
    ...profile.achievements.map((x) => ({ section: "achievements" as const, id: x.id, title: x.title, subtitle: join(x.organization, monthYear(x.achieved_on)), status: x.verification_status })),
    ...profile.facts.map((x) => ({ section: "facts" as const, id: x.id, title: x.fact, subtitle: titleCase(x.category), status: x.verification_status })),
    ...profile.answers.map((x) => ({ section: "answers" as const, id: x.id, title: x.question, subtitle: titleCase(x.category), status: x.verification_status })),
  ];
}

export default function ProfileScreen() {
  const theme = useTheme();
  const { colors } = theme;
  const profile = useProfile();
  const verify = useVerify();
  const refresh = useRefresh(() => profile.refetch());

  if (profile.isPending) {
    return (
      <Screen title="Profile">
        <Loading />
      </Screen>
    );
  }
  if (profile.isError) {
    return (
      <Screen title="Profile" refresh={refresh}>
        <Card>
          <EmptyState
            icon="cloud-offline-outline"
            title="Couldn't load your profile"
            message={profile.error.message}
            action={<Button label="Try Again" variant="tinted" size="medium" onPress={() => void profile.refetch()} />}
          />
        </Card>
      </Screen>
    );
  }

  const data = profile.data;
  const { basics, stats } = data;
  const pending = flatten(data).filter((item) => item.status === "UNVERIFIED" || item.status === "OUTDATED");
  const pendingSkills = pending.filter((item) => item.section === "skills");
  const name = basics.full_name ?? "Your profile";
  const initials = name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  const busyIds = verify.isPending ? (verify.variables?.ids ?? []) : [];

  const decide = (item: Item, status: "VERIFIED" | "REJECTED") => {
    theme.haptic(status === "VERIFIED" ? "success" : "warning");
    verify.mutate({ section: item.section, ids: [item.id], status });
  };

  const verifyAllSkills = () =>
    Alert.alert(
      "Verify all skills?",
      `This confirms ${pendingSkills.length} skills are accurate. Only verified skills are used for matching and resumes.`,
      [
        { text: "Cancel", style: "cancel" },
        { text: "Verify All", onPress: () => verify.mutate({ section: "skills", ids: pendingSkills.map((item) => item.id), status: "VERIFIED" }) },
      ],
    );

  return (
    <Screen title="Profile" refresh={refresh}>
      <View style={styles.identity}>
        <View style={[styles.avatar, { backgroundColor: theme.accent }]}>
          <T v="title1" color="#FFFFFF">
            {initials || "?"}
          </T>
        </View>
        <T v="title2" style={{ textAlign: "center" }}>
          {name}
        </T>
        {basics.headline || basics.current_role ? (
          <T v="subhead" color={colors.text2} style={{ textAlign: "center" }}>
            {basics.headline ?? basics.current_role}
          </T>
        ) : null}
        {basics.location ? (
          <T v="footnote" color={colors.text2}>
            {basics.location}
          </T>
        ) : null}
      </View>

      <Card>
        <View style={{ gap: theme.space.sm }}>
          <View style={styles.between}>
            <T v="headline">Profile strength</T>
            <T v="headline" color={stats.completeness >= 80 ? colors.success : theme.accent}>
              {stats.completeness}%
            </T>
          </View>
          <Bar value={stats.completeness / 100} color={stats.completeness >= 80 ? "#34C759" : theme.accent} />
          <T v="footnote" color={colors.text2}>
            {stats.verified_items} verified · {stats.unverified_items} to review · {stats.outdated_items} outdated
          </T>
        </View>
      </Card>

      <Group header="Checklist">
        {stats.checklist.map((check) => (
          <Row
            key={check.key}
            title={check.label}
            numberOfLines={2}
            right={
              <Ionicons name={check.done ? "checkmark-circle" : "ellipse-outline"} size={22} color={check.done ? "#34C759" : colors.text3} />
            }
          />
        ))}
      </Group>

      {pending.length === 0 ? (
        <Group header="Review" footer="CareerOS only uses verified facts for matching, resumes and messages. It never invents anything.">
          <Row icon="shield-checkmark" iconColor="#34C759" title="Everything is verified" />
        </Group>
      ) : (
        <Group
          header={`Needs your review · ${pending.length}`}
          footer="Confirm what's accurate. Rejected items are never used."
          action={
            pendingSkills.length > 1 ? (
              <Button label="Verify All Skills" variant="plain" size="small" onPress={verifyAllSkills} style={{ height: 22, paddingHorizontal: 0 }} />
            ) : undefined
          }
        >
          {pending.map((item) => (
            <Row
              key={item.id}
              title={item.title}
              subtitle={[SECTION_LABELS[item.section], item.subtitle, item.status === "OUTDATED" ? "Outdated" : null].filter(Boolean).join(" · ")}
              numberOfLines={3}
              right={
                busyIds.includes(item.id) ? (
                  <ActivityIndicator color={colors.text2} />
                ) : (
                  <View style={styles.decide}>
                    <IconButton icon="close" label={`Reject ${item.title}`} tint={colors.danger} onPress={() => decide(item, "REJECTED")} />
                    <IconButton icon="checkmark" label={`Verify ${item.title}`} filled tint="#34C759" onPress={() => decide(item, "VERIFIED")} />
                  </View>
                )
              }
            />
          ))}
        </Group>
      )}

      {data.experience.length > 0 ? (
        <Group header="Experience">
          {data.experience.map((x) => (
            <Row key={x.id} title={x.role} subtitle={`${x.organization} · ${span(x.start_date, x.end_date, x.is_current)}`} />
          ))}
        </Group>
      ) : null}

      {data.projects.length > 0 ? (
        <Group header="Projects">
          {data.projects.map((x) => (
            <Row key={x.id} title={x.name} subtitle={x.technologies.join(" · ") || null} />
          ))}
        </Group>
      ) : null}

      {data.education.length > 0 ? (
        <Group header="Education">
          {data.education.map((x) => (
            <Row key={x.id} title={x.field ? `${x.degree}, ${x.field}` : x.degree} subtitle={`${x.institution} · ${span(x.start_date, x.end_date, x.is_current)}`} numberOfLines={2} />
          ))}
        </Group>
      ) : null}

      {data.skills.length > 0 ? (
        <View style={{ gap: 7 }}>
          <T v="footnote" color={colors.text2} style={{ paddingHorizontal: 16, textTransform: "uppercase" }}>
            Skills
          </T>
          <Card>
            <View style={styles.skills}>
              {data.skills
                .filter((skill) => skill.verification_status !== "REJECTED")
                .map((skill) => (
                  <Chip key={skill.id} label={skill.name} tone={skill.verification_status === "VERIFIED" ? "accent" : "neutral"} />
                ))}
            </View>
          </Card>
          <T v="footnote" color={colors.text2} style={{ paddingHorizontal: 16 }}>
            Tinted skills are verified. Add or edit details from the CareerOS web app.
          </T>
        </View>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  identity: { alignItems: "center", gap: 4 },
  avatar: { width: 84, height: 84, borderRadius: 42, alignItems: "center", justifyContent: "center", marginBottom: 8 },
  between: { flexDirection: "row", justifyContent: "space-between", alignItems: "baseline" },
  decide: { flexDirection: "row", gap: 8 },
  skills: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
});
