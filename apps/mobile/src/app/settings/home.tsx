import { View } from "react-native";

import { Screen } from "@/components/screen";
import { OptionGroup } from "@/components/settings-kit";
import { Group, IconButton, type IconName, Row, Segmented, SwitchRow, Toggle } from "@/components/ui";
import { type HomeSection, type StartTab, usePrefs } from "@/lib/prefs";

const SECTIONS: Record<HomeSection, { label: string; icon: IconName; color: string }> = {
  stats: { label: "Quick stats", icon: "grid", color: "#007AFF" },
  alerts: { label: "Notifications", icon: "notifications", color: "#FF3B30" },
  topMatches: { label: "Top matches", icon: "star", color: "#5856D6" },
  deadlines: { label: "Closing soon", icon: "time", color: "#FF9500" },
  activity: { label: "Agent activity", icon: "pulse", color: "#34C759" },
};

const START_TABS: { value: StartTab; label: string }[] = [
  { value: "index", label: "Today" },
  { value: "jobs", label: "Jobs" },
  { value: "alerts", label: "Alerts" },
  { value: "profile", label: "Profile" },
];

export default function HomeSettingsScreen() {
  const { prefs, set } = usePrefs();

  const move = (index: number, delta: -1 | 1) => {
    const order = [...prefs.homeOrder];
    const target = index + delta;
    if (target < 0 || target >= order.length) return;
    [order[index], order[target]] = [order[target], order[index]];
    set({ homeOrder: order });
  };

  const toggle = (section: HomeSection, visible: boolean) =>
    set({ homeHidden: visible ? prefs.homeHidden.filter((s) => s !== section) : [...prefs.homeHidden, section] });

  return (
    <Screen title="Today Screen" back="Settings" backFallback="/settings" tabBar={false}>
      <Group header="Sections" footer="Choose what the Today screen shows and in which order.">
        {prefs.homeOrder.map((section, index) => (
          <Row
            key={section}
            icon={SECTIONS[section].icon}
            iconColor={SECTIONS[section].color}
            title={SECTIONS[section].label}
            right={
              <View style={{ flexDirection: "row", alignItems: "center", gap: 6 }}>
                <IconButton icon="chevron-up" label={`Move ${SECTIONS[section].label} up`} size={30} disabled={index === 0} onPress={() => move(index, -1)} />
                <IconButton
                  icon="chevron-down"
                  label={`Move ${SECTIONS[section].label} down`}
                  size={30}
                  disabled={index === prefs.homeOrder.length - 1}
                  onPress={() => move(index, 1)}
                />
                <Toggle label={`Show ${SECTIONS[section].label}`} value={!prefs.homeHidden.includes(section)} onChange={(v) => toggle(section, v)} />
              </View>
            }
          />
        ))}
      </Group>

      <Group header="Header">
        <SwitchRow title="Personal Greeting" subtitle="“Good morning, …” instead of “Today”." value={prefs.greeting} onChange={(greeting) => set({ greeting })} />
      </Group>

      <Group header="Notifications on Today">
        <Row
          title="Style"
          right={
            <View style={{ width: 170 }}>
              <Segmented
                options={[
                  { value: "stack", label: "Stack" },
                  { value: "list", label: "List" },
                ]}
                value={prefs.alertsStyle}
                onChange={(alertsStyle) => set({ alertsStyle })}
              />
            </View>
          }
        />
      </Group>

      <OptionGroup header="Open app on" options={START_TABS} value={prefs.startTab} onChange={(startTab) => set({ startTab })} footer="Takes effect the next time you open CareerOS." />
    </Screen>
  );
}
