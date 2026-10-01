import * as Application from "expo-application";
import { router } from "expo-router";
import { Alert, StyleSheet, View } from "react-native";

import { Screen } from "@/components/screen";
import { Group, Row, T } from "@/components/ui";
import { useMe, useSources } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { useEmailAccount } from "@/lib/email";
import { usePrefs } from "@/lib/prefs";
import { ACCENTS, useTheme } from "@/lib/theme";

export default function SettingsScreen() {
  const theme = useTheme();
  const auth = useAuth();
  const me = useMe();
  const sources = useSources();
  const emailAccount = useEmailAccount();
  const { prefs, reset } = usePrefs();

  const name = me.data?.name ?? auth.session?.name ?? "Your account";
  const email = me.data?.email ?? auth.session?.email ?? "";
  const initials = name
    .split(/\s+/)
    .map((part) => part[0])
    .join("")
    .slice(0, 2)
    .toUpperCase();
  const failing = sources.data?.filter((s) => s.health === "failing" || s.health === "degraded").length ?? 0;

  const confirmSignOut = () =>
    Alert.alert("Sign Out?", "You'll need your password to sign in again.", [
      { text: "Cancel", style: "cancel" },
      { text: "Sign Out", style: "destructive", onPress: () => void auth.signOut() },
    ]);

  const confirmReset = () =>
    Alert.alert("Reset All Preferences?", "Appearance, layout and list settings return to their defaults. Server settings are not affected.", [
      { text: "Cancel", style: "cancel" },
      { text: "Reset", style: "destructive", onPress: () => reset() },
    ]);

  return (
    <Screen title="Settings" back="Profile" tabBar={false}>
      <Group>
        <Row
          title={name}
          subtitle={email}
          onPress={() => router.push("/settings/account")}
          chevron
          left={
            <View style={[styles.avatar, { backgroundColor: theme.accent }]}>
              <T v="title3" color="#FFFFFF">
                {initials || "?"}
              </T>
            </View>
          }
        />
      </Group>

      <Group>
        <Row icon="color-palette" iconColor="#007AFF" title="Appearance" value={ACCENTS[prefs.accent].label} chevron onPress={() => router.push("/settings/appearance")} />
        <Row icon="today" iconColor="#FF9500" title="Today Screen" chevron onPress={() => router.push("/settings/home")} />
        <Row icon="briefcase" iconColor="#5856D6" title="Jobs & Matches" chevron onPress={() => router.push("/settings/jobs")} />
        <Row icon="notifications" iconColor="#FF3B30" title="Notifications & Data" chevron onPress={() => router.push("/settings/notifications")} />
      </Group>

      <Group footer="These settings live on the server and change what the agent looks for and how it scores roles.">
        <Row icon="search" iconColor="#34C759" title="Job Search Preferences" chevron onPress={() => router.push("/settings/search")} />
        <Row
          icon="mail"
          iconColor="#EA4335"
          title="Email"
          value={emailAccount.data ? (emailAccount.data.connected ? "Gmail connected" : emailAccount.data.status === "ERROR" ? "Reconnect" : "Not connected") : null}
          chevron
          onPress={() => router.push("/settings/email")}
        />
        <Row
          icon="globe"
          iconColor="#30B0C7"
          title="Job Sources"
          value={failing > 0 ? `${failing} need attention` : sources.data ? String(sources.data.length) : null}
          chevron
          onPress={() => router.push("/settings/sources")}
        />
      </Group>

      <Group header="Safety" footer="CareerOS never submits applications or sends emails without your explicit approval, and never invents facts about you.">
        <Row icon="paper-plane" iconColor="#8E8E93" title="Auto-submit applications" value="Off" />
        <Row icon="mail" iconColor="#8E8E93" title="Auto-send emails" value="Off" />
      </Group>

      <Group>
        <Row title="Version" value={`${Application.nativeApplicationVersion ?? "dev"} (${Application.nativeBuildVersion ?? "0"})`} />
        <Row title="Reset All Preferences" destructive onPress={confirmReset} />
      </Group>

      <Group>
        <Row title="Sign Out" destructive onPress={confirmSignOut} />
      </Group>
    </Screen>
  );
}

const styles = StyleSheet.create({
  avatar: { width: 58, height: 58, borderRadius: 29, marginVertical: 8, alignItems: "center", justifyContent: "center" },
});
