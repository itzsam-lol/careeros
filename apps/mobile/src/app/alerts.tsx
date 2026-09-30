import { router } from "expo-router";
import { useState } from "react";
import { Pressable, View } from "react-native";

import { NotificationContent } from "@/components/notification-stack";
import { Screen, useRefresh } from "@/components/screen";
import { Button, Card, EmptyState, Loading, Segmented } from "@/components/ui";
import { type Notification, useMarkRead, useNotifications } from "@/lib/api";
import { useTheme } from "@/lib/theme";

export default function AlertsScreen() {
  const theme = useTheme();
  const notifications = useNotifications();
  const markRead = useMarkRead();
  const refresh = useRefresh(() => notifications.refetch());
  const [filter, setFilter] = useState<"all" | "unread">("all");
  const items = notifications.data ?? [];
  const unread = items.filter((n) => !n.read).length;
  const shown = filter === "unread" ? items.filter((n) => !n.read) : items;

  const open = (notification: Notification) => {
    if (!notification.read && theme.prefs.markReadOnOpen) markRead.mutate([notification.id]);
    if (notification.job_id) router.push({ pathname: "/job/[id]", params: { id: notification.job_id } });
    else if (!notification.read) markRead.mutate([notification.id]);
  };

  return (
    <Screen
      back="Today"
      tabBar={false}
      title="Alerts"
      subtitle={unread > 0 ? `${unread} unread` : "You're all caught up"}
      refresh={refresh}
      accessory={
        unread > 0 ? (
          <Button label="Read All" variant="tinted" size="small" onPress={() => markRead.mutate(undefined)} loading={markRead.isPending} />
        ) : undefined
      }
    >
      <Segmented
        options={[
          { value: "all", label: "All" },
          { value: "unread", label: unread > 0 ? `Unread (${unread})` : "Unread" },
        ]}
        value={filter}
        onChange={setFilter}
      />
      {notifications.isPending ? (
        <Loading />
      ) : notifications.isError ? (
        <Card>
          <EmptyState
            icon="cloud-offline-outline"
            title="Couldn't load alerts"
            message={notifications.error.message}
            action={<Button label="Try Again" variant="tinted" size="medium" onPress={() => void notifications.refetch()} />}
          />
        </Card>
      ) : shown.length === 0 ? (
        <EmptyState
          icon="notifications-outline"
          title={filter === "unread" ? "No unread alerts" : "No alerts yet"}
          message="High matches, deadlines and anything that needs your approval will show up here."
        />
      ) : (
        <View style={{ gap: theme.space.sm }}>
          {shown.map((notification) => (
            <Pressable
              key={notification.id}
              accessibilityRole="button"
              accessibilityLabel={`${notification.read ? "" : "Unread. "}${notification.title}`}
              onPress={() => {
                theme.haptic("select");
                open(notification);
              }}
              style={({ pressed }) => [
                theme.card,
                { borderRadius: theme.radius.card + 4, padding: theme.space.lg, opacity: pressed ? 0.75 : 1 },
              ]}
            >
              <NotificationContent notification={notification} lines={3} />
            </Pressable>
          ))}
        </View>
      )}
    </Screen>
  );
}
