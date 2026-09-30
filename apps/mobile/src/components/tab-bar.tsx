import Ionicons from "@expo/vector-icons/Ionicons";
import { BlurView } from "expo-blur";
import type { BottomTabBarProps } from "expo-router/tabs";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";

import type { IconName } from "@/components/ui";
import { useUnreadCount } from "@/lib/api";
import { useTheme } from "@/lib/theme";

const ICONS: Record<string, [IconName, IconName]> = {
  index: ["today", "today-outline"],
  jobs: ["briefcase", "briefcase-outline"],
  tracker: ["git-network", "git-network-outline"],
  resumes: ["document-text", "document-text-outline"],
  profile: ["person-circle", "person-circle-outline"],
};

/** Bottom tab bar in the style of UITabBar: translucent, hairline on top, accent tint. */
export function AppTabBar({ state, descriptors, navigation, insets }: BottomTabBarProps) {
  const theme = useTheme();
  const unread = useUnreadCount().data?.unread ?? 0;
  const labels = theme.prefs.tabLabels;

  return (
    <View style={[styles.bar, { paddingBottom: Math.max(insets.bottom, 6), borderTopColor: theme.colors.separator }]}>
      {Platform.OS === "ios" ? (
        <BlurView intensity={80} tint="systemChromeMaterialLight" style={StyleSheet.absoluteFill} />
      ) : null}
      <View style={[StyleSheet.absoluteFill, { backgroundColor: Platform.OS === "ios" ? "rgba(249,249,249,0.6)" : "rgba(250,250,252,0.97)" }]} />
      <View style={styles.row}>
        {state.routes.map((route, index) => {
          const focused = state.index === index;
          const label = descriptors[route.key]?.options.title ?? route.name;
          const [active, inactive] = ICONS[route.name] ?? ["ellipse", "ellipse-outline"];
          const icon = focused ? active : inactive;
          const color = focused ? theme.accent : "#8E8E93";
          const badge = route.name === "index" && unread > 0 ? (unread > 99 ? "99+" : String(unread)) : null;
          return (
            <Pressable
              key={route.key}
              accessibilityRole="tab"
              accessibilityState={{ selected: focused }}
              accessibilityLabel={badge ? `${label}, ${badge} unread` : label}
              onPress={() => {
                const event = navigation.emit({ type: "tabPress", target: route.key, canPreventDefault: true });
                if (!focused && !event.defaultPrevented) {
                  theme.haptic("select");
                  navigation.navigate(route.name, route.params);
                }
              }}
              onLongPress={() => navigation.emit({ type: "tabLongPress", target: route.key })}
              style={[styles.tab, { paddingVertical: labels ? 5 : 11 }]}
            >
              <View>
                <Ionicons name={icon} size={labels ? 25 : 27} color={color} />
                {badge ? (
                  <View style={[styles.badge, { backgroundColor: "#FF3B30" }]}>
                    <Text style={styles.badgeText}>{badge}</Text>
                  </View>
                ) : null}
              </View>
              {labels ? (
                <Text style={[theme.type.caption2, { color, fontSize: 10, lineHeight: 12, letterSpacing: 0.1 }]} numberOfLines={1}>
                  {label}
                </Text>
              ) : null}
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  bar: { position: "absolute", left: 0, right: 0, bottom: 0, borderTopWidth: StyleSheet.hairlineWidth, overflow: "hidden" },
  row: { flexDirection: "row" },
  tab: { flex: 1, alignItems: "center", gap: 2 },
  badge: {
    position: "absolute",
    top: -3,
    left: 16,
    minWidth: 18,
    height: 18,
    borderRadius: 9,
    paddingHorizontal: 5,
    alignItems: "center",
    justifyContent: "center",
  },
  badgeText: { color: "#fff", fontSize: 11, fontWeight: "600" },
});
