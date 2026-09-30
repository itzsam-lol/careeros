import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import { Pressable, StyleSheet, View } from "react-native";

import { JobCardView, useJobFilter } from "@/components/job-card";
import { NotificationStack } from "@/components/notification-stack";
import { HeaderButton, Screen, useRefresh } from "@/components/screen";
import { Button, Card, EmptyState, Group, type IconName, Loading, Row, T } from "@/components/ui";
import { type JobView, type Notification, useDashboard, useMarkRead, useMe, useUnreadCount } from "@/lib/api";
import { useWhen } from "@/lib/format";
import type { HomeSection } from "@/lib/prefs";
import { useTheme } from "@/lib/theme";

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 5) return "Good night";
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}

function SectionHeader({ title, action, onAction }: { title: string; action?: string; onAction?: () => void }) {
  const theme = useTheme();
  return (
    <View style={styles.sectionHeader}>
      <T v="title3">{title}</T>
      {action && onAction ? (
        <Pressable accessibilityRole="button" hitSlop={10} onPress={onAction}>
          <T v="body" color={theme.accent}>
            {action}
          </T>
        </Pressable>
      ) : null}
    </View>
  );
}

function StatTile({ label, value, icon, color, onPress }: { label: string; value: number | string; icon: IconName; color: string; onPress: () => void }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`${label}: ${value}`}
      onPress={() => {
        theme.haptic("select");
        onPress();
      }}
      style={({ pressed }) => [theme.card, styles.tile, { borderRadius: theme.radius.card, padding: theme.space.lg, opacity: pressed ? 0.7 : 1 }]}
    >
      <View style={styles.tileTop}>
        <View style={[styles.tileIcon, { backgroundColor: color }]}>
          <Ionicons name={icon} size={15} color="#FFFFFF" />
        </View>
        <T v="title1" style={{ fontVariant: ["tabular-nums"] }}>
          {value}
        </T>
      </View>
      <T v="subhead" color={theme.colors.text2} numberOfLines={1}>
        {label}
      </T>
    </Pressable>
  );
}

export default function TodayScreen() {
  const theme = useTheme();
  const { prefs } = theme;
  const me = useMe();
  const dashboard = useDashboard();
  const markRead = useMarkRead();
  const when = useWhen();
  const keep = useJobFilter();
  const unread = useUnreadCount().data?.unread ?? 0;
  const refresh = useRefresh(() => Promise.all([dashboard.refetch(), me.refetch()]));

  const openJobs = (view: JobView) => router.navigate({ pathname: "/jobs", params: { view } });
  const openNotification = (notification: Notification) => {
    if (!notification.read && prefs.markReadOnOpen) markRead.mutate([notification.id]);
    if (notification.job_id) router.push({ pathname: "/job/[id]", params: { id: notification.job_id } });
    else router.navigate("/alerts");
  };

  const firstName = me.data?.name?.split(" ")[0];
  const data = dashboard.data;
  const counts = data?.counts ?? {};
  const date = new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" });

  const sections: Record<HomeSection, React.ReactNode> = data
    ? {
        stats: (
          <View style={[styles.grid, { gap: theme.space.md }]}>
            <StatTile label="New roles" value={counts.new ?? 0} icon="sparkles" color="#007AFF" onPress={() => openJobs("NEW")} />
            <StatTile label="High matches" value={counts.high_match ?? 0} icon="star" color="#5856D6" onPress={() => openJobs("HIGH_MATCH")} />
            <StatTile label="Closing soon" value={counts.deadline_soon ?? 0} icon="time" color="#FF3B30" onPress={() => openJobs("DEADLINE_SOON")} />
            <StatTile label="Saved" value={counts.saved ?? 0} icon="bookmark" color="#FF9500" onPress={() => openJobs("SAVED")} />
            <StatTile label="Applying" value={counts.applied ?? 0} icon="paper-plane" color="#34C759" onPress={() => router.navigate("/tracker")} />
            <StatTile label="Unread alerts" value={counts.unread_notifications ?? 0} icon="notifications" color="#AF52DE" onPress={() => router.push("/alerts")} />
          </View>
        ),
        alerts:
          data.notifications.length > 0 ? (
            <View style={{ gap: theme.space.md }}>
              <SectionHeader title="Notifications" action="See All" onAction={() => router.navigate("/alerts")} />
              <NotificationStack notifications={data.notifications} onOpen={openNotification} />
            </View>
          ) : null,
        topMatches: (
          <View style={{ gap: theme.space.md }}>
            <SectionHeader title="Top matches" action="See All" onAction={() => openJobs("ALL")} />
            {data.top_matches.filter(keep).length === 0 ? (
              <Card>
                <EmptyState icon="sparkles-outline" title="No matches yet" message="Matches appear here as soon as the agent analyses new roles." />
              </Card>
            ) : (
              data.top_matches.filter(keep).map((job) => <JobCardView key={job.job_id} job={job} />)
            )}
          </View>
        ),
        deadlines:
          data.upcoming_deadlines.filter(keep).length > 0 ? (
            <View style={{ gap: theme.space.md }}>
              <SectionHeader title="Closing soon" action="See All" onAction={() => openJobs("DEADLINE_SOON")} />
              {data.upcoming_deadlines.filter(keep).map((job) => (
                <JobCardView key={job.job_id} job={job} compact />
              ))}
            </View>
          ) : null,
        activity: (
          <View style={{ gap: theme.space.md }}>
            <SectionHeader title="Agent activity" />
            <Group footer="Everything the agent does is logged here.">
              {data.recent_activity.length === 0 ? (
                <Row title="Nothing yet" subtitle="Add a job source to get the agent started." />
              ) : (
                data.recent_activity.map((event) => <Row key={event.id} title={event.summary} value={when(event.created_at)} numberOfLines={2} />)
              )}
            </Group>
          </View>
        ),
      }
    : ({} as Record<HomeSection, React.ReactNode>);

  return (
    <Screen
      title={prefs.greeting ? `${greeting()}${firstName ? `, ${firstName}` : ""}` : "Today"}
      subtitle={date}
      refresh={refresh}
      accessory={<HeaderButton icon="notifications-outline" label="Alerts" badge={unread} onPress={() => router.push("/alerts")} />}
    >
      {dashboard.isPending ? (
        <Loading />
      ) : dashboard.isError ? (
        <Card>
          <EmptyState
            icon="cloud-offline-outline"
            title="Can't reach CareerOS"
            message={dashboard.error.message}
            action={<Button label="Try Again" variant="tinted" size="medium" onPress={() => void dashboard.refetch()} />}
          />
        </Card>
      ) : data ? (
        <>
          {data.profile.completeness < 80 || data.sources.total === 0 ? (
            <Group>
              {data.profile.completeness < 80 ? (
                <Row
                  icon="person"
                  iconColor="#34C759"
                  title={`Profile ${data.profile.completeness}% complete`}
                  subtitle="Matches and resumes only use what you have verified."
                  chevron
                  onPress={() => router.navigate("/profile")}
                />
              ) : null}
              {data.sources.total === 0 ? (
                <Row
                  icon="globe"
                  iconColor="#007AFF"
                  title="Add a job source"
                  subtitle="Company boards or feeds the agent should watch."
                  chevron
                  onPress={() => router.push("/settings/sources")}
                />
              ) : null}
            </Group>
          ) : null}
          {prefs.homeOrder
            .filter((key) => !prefs.homeHidden.includes(key))
            .map((key) => (sections[key] ? <View key={key}>{sections[key]}</View> : null))}
        </>
      ) : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  sectionHeader: { flexDirection: "row", alignItems: "baseline", justifyContent: "space-between", paddingHorizontal: 2 },
  grid: { flexDirection: "row", flexWrap: "wrap" },
  tile: { flexBasis: "46%", flexGrow: 1, gap: 6 },
  tileTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  tileIcon: { width: 28, height: 28, borderRadius: 14, alignItems: "center", justifyContent: "center" },
});
