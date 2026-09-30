import { useState } from "react";
import { Pressable, StyleSheet, View } from "react-native";
import Animated, { FadeIn, LinearTransition } from "react-native-reanimated";

import { IconSquare, type IconName, T } from "@/components/ui";
import type { Notification } from "@/lib/api";
import { useWhen } from "@/lib/format";
import { type Theme, useTheme } from "@/lib/theme";

export function notificationStyle(theme: Theme, type: Notification["type"]): { icon: IconName; label: string; color: string } {
  switch (type) {
    case "HIGH_MATCH":
      return { icon: "sparkles", label: "High match", color: "#5856D6" };
    case "NEW_JOB":
      return { icon: "briefcase", label: "New match", color: "#007AFF" };
    case "DEADLINE_SOON":
      return { icon: "calendar", label: "Deadline", color: "#FF3B30" };
    case "RESUME_READY":
      return { icon: "document-text", label: "Resume ready", color: "#34C759" };
    case "OUTREACH_APPROVAL_REQUIRED":
    case "APPLICATION_NEEDS_INPUT":
      return { icon: "hand-left", label: "Needs you", color: "#FF9500" };
    case "SOURCE_FAILING":
      return { icon: "warning", label: "Source issue", color: "#FF9500" };
    default:
      return { icon: "notifications", label: "Update", color: theme.colors.text2 };
  }
}

export function NotificationContent({ notification, lines = 2 }: { notification: Notification; lines?: number }) {
  const theme = useTheme();
  const when = useWhen();
  const style = notificationStyle(theme, notification.type);
  return (
    <View style={{ gap: 4 }}>
      <View style={styles.top}>
        <IconSquare icon={style.icon} color={style.color} size={20} />
        <T v="footnote" color={theme.colors.text2} style={{ flex: 1, textTransform: "uppercase", letterSpacing: 0.3 }} numberOfLines={1}>
          {style.label}
        </T>
        {!notification.read ? <View style={[styles.dot, { backgroundColor: theme.accent }]} /> : null}
        <T v="footnote" color={theme.colors.text2}>
          {when(notification.created_at)}
        </T>
      </View>
      <T v="headline" numberOfLines={2}>
        {notification.title}
      </T>
      {notification.body && lines > 0 ? (
        <T v="subhead" color={theme.colors.text2} numberOfLines={lines}>
          {notification.body}
        </T>
      ) : null}
    </View>
  );
}

/**
 * Latest notifications as an iOS-style grouped stack: the newest card in front with the
 * others peeking out beneath it. Tapping the stack expands it; tapping a card opens it.
 */
export function NotificationStack({
  notifications,
  onOpen,
}: {
  notifications: Notification[];
  onOpen: (notification: Notification) => void;
}) {
  const theme = useTheme();
  const listMode = theme.prefs.alertsStyle === "list";
  const [expanded, setExpanded] = useState(false);
  const latest = notifications.slice(0, 3);
  if (latest.length === 0) return null;
  const open = listMode || expanded || latest.length === 1;
  const layout = theme.prefs.reduceMotion ? undefined : LinearTransition.springify().damping(20).stiffness(180);

  return (
    <View style={{ gap: theme.space.sm }}>
      <View style={{ paddingBottom: open ? 0 : (latest.length - 1) * 8 }}>
        {/* Collapsed: draw the back cards first so the newest one sits on top (Android z-order). */}
        {(open ? latest : [...latest].reverse()).map((notification) => {
          const index = latest.indexOf(notification);
          const behind = !open && index > 0;
          return (
            <Animated.View
              key={notification.id}
              layout={layout}
              entering={theme.prefs.reduceMotion ? undefined : FadeIn.duration(200)}
              style={[
                behind
                  ? {
                      position: "absolute",
                      top: index * 8,
                      bottom: -index * 8,
                      left: index * 10,
                      right: index * 10,
                      opacity: 1 - index * 0.25,
                    }
                  : { marginTop: index > 0 ? theme.space.sm : 0 },
              ]}
            >
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={behind ? "Show more notifications" : notification.title}
                onPress={() => {
                  if (!open) {
                    theme.haptic("light");
                    setExpanded(true);
                  } else {
                    onOpen(notification);
                  }
                }}
                style={({ pressed }) => [
                  styles.card,
                  theme.card,
                  { borderRadius: theme.radius.card + 4, padding: theme.space.lg, opacity: pressed ? 0.8 : 1 },
                  behind && { flex: 1 },
                ]}
              >
                {behind ? null : <NotificationContent notification={notification} />}
              </Pressable>
            </Animated.View>
          );
        })}
      </View>
      {!listMode && latest.length > 1 ? (
        <Pressable
          accessibilityRole="button"
          onPress={() => {
            theme.haptic("select");
            setExpanded((value) => !value);
          }}
          hitSlop={8}
          style={{ alignSelf: "center" }}
        >
          <T v="footnote" color={theme.accent}>
            {expanded ? "Show less" : `${latest.length - 1} more`}
          </T>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: "row", alignItems: "center", gap: 8 },
  dot: { width: 8, height: 8, borderRadius: 4 },
  card: { overflow: "hidden" },
});
