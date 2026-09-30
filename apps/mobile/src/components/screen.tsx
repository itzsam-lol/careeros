import Ionicons from "@expo/vector-icons/Ionicons";
import { router } from "expo-router";
import { useState } from "react";
import { Pressable, RefreshControl, ScrollView, StyleSheet, View, type ViewStyle } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { T } from "@/components/ui";
import { useTheme } from "@/lib/theme";

/** Vertical room reserved for the tab bar. */
export const TAB_BAR_SPACE = 64;

export interface Refresh {
  refreshing: boolean;
  onRefresh: () => void;
}

/** Pull-to-refresh state that only spins for user-initiated refreshes (not background polling). */
export function useRefresh(refetch: () => Promise<unknown>): Refresh {
  const [refreshing, setRefreshing] = useState(false);
  const onRefresh = () => {
    setRefreshing(true);
    refetch()
      .catch(() => undefined)
      .finally(() => setRefreshing(false));
  };
  return { refreshing, onRefresh };
}

export function useRefreshControl(refresh: Refresh | undefined, offset = 0) {
  const theme = useTheme();
  if (!refresh) return undefined;
  return (
    <RefreshControl
      refreshing={refresh.refreshing}
      onRefresh={refresh.onRefresh}
      tintColor={theme.colors.text2}
      colors={[theme.accent]}
      progressBackgroundColor="#FFFFFF"
      progressViewOffset={offset}
    />
  );
}

/** "‹ Back" in the accent colour, like a UINavigationBar back button. */
export function BackButton({ label = "Back", fallback = "/" }: { label?: string; fallback?: "/" | "/jobs" | "/settings" }) {
  const theme = useTheme();
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={`Back to ${label}`}
      hitSlop={12}
      onPress={() => (router.canGoBack() ? router.back() : router.replace(fallback))}
      style={({ pressed }) => [styles.back, { opacity: pressed ? 0.5 : 1 }]}
    >
      <Ionicons name="chevron-back" size={26} color={theme.accent} style={{ marginLeft: -8 }} />
      <T v="body" color={theme.accent}>
        {label}
      </T>
    </Pressable>
  );
}

interface ScreenProps {
  title?: string;
  subtitle?: string;
  /** Element shown to the right of the large title (e.g. a button). */
  accessory?: React.ReactNode;
  /** Label for the back button on pushed screens; omit on tab roots. */
  back?: string;
  backFallback?: "/" | "/jobs" | "/settings";
  children: React.ReactNode;
  refresh?: Refresh;
  tabBar?: boolean;
  contentStyle?: ViewStyle;
}

export function Screen({ title, subtitle, accessory, back, backFallback, children, refresh, tabBar = true, contentStyle }: ScreenProps) {
  const theme = useTheme();
  const insets = useSafeAreaInsets();
  const refreshControl = useRefreshControl(refresh);
  return (
    <View style={[styles.root, { backgroundColor: theme.colors.background }]}>
      <ScrollView
        contentContainerStyle={[
          {
            paddingTop: insets.top + (back ? 4 : theme.space.md),
            paddingBottom: (tabBar ? TAB_BAR_SPACE : theme.space.xl) + insets.bottom + theme.space.lg,
            paddingHorizontal: theme.space.lg,
            gap: theme.space.xl,
          },
          contentStyle,
        ]}
        refreshControl={refreshControl}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode="on-drag"
      >
        {back || title ? (
          <View style={{ gap: 2, marginBottom: -theme.space.sm }}>
            {back ? <BackButton label={back} fallback={backFallback} /> : null}
            {title ? (
              <View style={styles.titleRow}>
                <T v="largeTitle" style={{ flex: 1 }} numberOfLines={2}>
                  {title}
                </T>
                {accessory}
              </View>
            ) : null}
            {subtitle ? (
              <T v="subhead" color={theme.colors.text2}>
                {subtitle}
              </T>
            ) : null}
          </View>
        ) : null}
        {children}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
  back: { flexDirection: "row", alignItems: "center", height: 44, alignSelf: "flex-start" },
  titleRow: { flexDirection: "row", alignItems: "center", gap: 12 },
});
