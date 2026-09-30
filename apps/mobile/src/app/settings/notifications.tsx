
import { Screen } from "@/components/screen";
import { SavingNote } from "@/components/settings-kit";
import { Button, Card, EmptyState, Group, Loading, Row, Segmented, StepperRow, SwitchRow } from "@/components/ui";
import { useServerSettings, useUpdateServerSettings } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";

const pct = (v: number) => `${Math.round(v * 100)}%`;

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

      <Group header="On this device">
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
    </Screen>
  );
}
