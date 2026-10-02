import { useCallback, useEffect, useState } from "react";
import { Alert, AppState, Linking } from "react-native";

import { Screen } from "@/components/screen";
import { SavingNote } from "@/components/settings-kit";
import { Button, Card, EmptyState, Group, Loading, Row, Segmented, StepperRow, SwitchRow } from "@/components/ui";
import { type AlertHealth, alertHealth, allowBackground, sendTestAlert } from "@/lib/alerts";
import { useServerSettings, useUpdateServerSettings } from "@/lib/api";
import { relativeTime } from "@/lib/format";
import { usePrefs } from "@/lib/prefs";
import { useTheme } from "@/lib/theme";

const pct = (v: number) => `${Math.round(v * 100)}%`;

/** How alerts reach this phone, and what can make them late. */
function DeliveryGroup() {
  const theme = useTheme();
  const [health, setHealth] = useState<AlertHealth | null>(null);
  const [testing, setTesting] = useState(false);
  const refresh = useCallback(() => void alertHealth().then(setHealth).catch(() => undefined), []);

  useEffect(() => {
    refresh();
    // Picks up the answer to Android's battery prompt when the user comes back.
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") refresh();
    });
    return () => subscription.remove();
  }, [refresh]);

  if (!health) return null;
  const instant = health.push?.active ?? false;
  const mode = instant ? "Instant" : health.scheduled ? "About every 15 min" : "Only while open";
  const sendTest = () => {
    setTesting(true);
    sendTestAlert()
      .then(() => theme.haptic("success"))
      .catch((error: Error) => Alert.alert("Couldn't send a test notification", error.message))
      .finally(() => setTesting(false));
  };

  return (
    <Group
      header="Delivery"
      footer={
        instant
          ? "New alerts are pushed to this phone the moment the agent finds them, even when the app is closed."
          : "This phone checks for new alerts in the background. Android runs the check about every 15 minutes when CareerOS may run in the background, and much less often when it doesn't."
      }
    >
      {health.allowed ? null : (
        <Row
          title="Turn On Notifications"
          subtitle="Notifications are off for CareerOS in Android settings, so alerts can't appear."
          numberOfLines={2}
          icon="notifications-off-outline"
          iconColor={theme.colors.danger}
          chevron
          onPress={() => void Linking.openSettings()}
        />
      )}
      <Row title="Alerts arrive" value={mode} />
      {instant ? null : (
        <Row
          title="Last background check"
          value={health.lastBackgroundCheck ? relativeTime(health.lastBackgroundCheck) : "Not yet"}
        />
      )}
      {health.restricted ? (
        <Row
          title="Allow Background Activity"
          subtitle="Android is pausing CareerOS to save battery, which can delay alerts by hours."
          numberOfLines={2}
          icon="battery-half-outline"
          iconColor={theme.colors.warning}
          chevron
          onPress={() => void allowBackground().catch(() => undefined).finally(refresh)}
        />
      ) : (
        <Row title="Background activity" value="Allowed" />
      )}
      <Row
        title={testing ? "Sending…" : "Send Test Notification"}
        icon="notifications-outline"
        iconColor="#FF3B30"
        disabled={testing}
        onPress={sendTest}
      />
    </Group>
  );
}

export default function NotificationSettingsScreen() {
  const { prefs, set } = usePrefs();
  const settings = useServerSettings();
  const update = useUpdateServerSettings();
  const matching = settings.data?.matching;
  const notifications = settings.data?.notifications;

  return (
    <Screen title="Notifications & Data" back="Settings" backFallback="/settings" tabBar={false}>
      {settings.isPending ? (
        <Loading />
      ) : settings.isError || !matching || !notifications ? (
        <Card>
          <EmptyState
            icon="cloud-offline-outline"
            title="Couldn't load settings"
            message={settings.error?.message}
            action={<Button label="Try Again" variant="tinted" size="medium" onPress={() => void settings.refetch()} />}
          />
        </Card>
      ) : (
        <>
          <Group header="Agent alerts" footer="The agent notifies you about roles at or above the alert threshold. High matches get their own filter and count.">
            <SwitchRow
              title="New Match Alerts"
              value={notifications.notify_new_jobs}
              onChange={(notify_new_jobs) => update.mutate({ notifications: { notify_new_jobs } })}
            />
            <StepperRow
              title="Alert threshold"
              subtitle="Minimum match score for an alert."
              value={matching.notify_threshold}
              min={0.3}
              max={0.95}
              step={0.05}
              format={pct}
              onChange={(notify_threshold) => update.mutate({ matching: { notify_threshold } })}
            />
            <StepperRow
              title="High match"
              subtitle="Score that counts as a high match."
              value={matching.high_match_threshold}
              min={0.5}
              max={0.95}
              step={0.05}
              format={pct}
              onChange={(high_match_threshold) => update.mutate({ matching: { high_match_threshold } })}
            />
          </Group>
          <SavingNote saving={update.isPending} error={update.error} />
        </>
      )}

      <Group
        header="On this device"
        footer="New alerts appear as notifications on this phone, and the app checks every minute while it's open."
      >
        <SwitchRow
          title="Phone Notifications"
          subtitle="Show new job alerts as notifications on this phone."
          value={prefs.phoneAlerts}
          onChange={(phoneAlerts) => set({ phoneAlerts })}
        />
        <SwitchRow
          title="Mark as Read When Opened"
          value={prefs.markReadOnOpen}
          onChange={(markReadOnOpen) => set({ markReadOnOpen })}
        />
        <Row
          title="Auto-refresh"
          subtitle="How often open screens check for updates."
          numberOfLines={2}
          below={<Segmented
                options={[
                  { value: 0, label: "Off" },
                  { value: 1, label: "1m" },
                  { value: 5, label: "5m" },
                  { value: 15, label: "15m" },
                ]}
                value={prefs.refreshMinutes}
                onChange={(refreshMinutes) => set({ refreshMinutes })}
              />}
        />
      </Group>
      {prefs.phoneAlerts ? <DeliveryGroup /> : null}
    </Screen>
  );
}
