import { View } from "react-native";

import { Screen } from "@/components/screen";
import { OptionGroup } from "@/components/settings-kit";
import { Group, Row, Segmented, StepperRow, SwitchRow } from "@/components/ui";
import { type JobViewPref, usePrefs } from "@/lib/prefs";

const VIEWS: { value: JobViewPref; label: string }[] = [
  { value: "NEW", label: "New" },
  { value: "HIGH_MATCH", label: "High match" },
  { value: "DEADLINE_SOON", label: "Closing soon" },
  { value: "SAVED", label: "Saved" },
  { value: "ALL", label: "All roles" },
];

function SegmentRow<V extends string>({ title, options, value, onChange, width = 210 }: { title: string; options: { value: V; label: string }[]; value: V; onChange: (v: V) => void; width?: number }) {
  return (
    <Row
      title={title}
      right={
        <View style={{ width }}>
          <Segmented options={options} value={value} onChange={onChange} />
        </View>
      }
    />
  );
}

export default function JobSettingsScreen() {
  const { prefs, set } = usePrefs();
  return (
    <Screen title="Jobs & Matches" back="Settings" backFallback="/settings" tabBar={false}>
      <OptionGroup header="Jobs tab opens on" options={VIEWS} value={prefs.defaultJobView} onChange={(defaultJobView) => set({ defaultJobView })} />

      <Group header="Sorting & scores">
        <SegmentRow
          title="Sort by"
          options={[
            { value: "SCORE", label: "Match" },
            { value: "RECENT", label: "Newest" },
            { value: "DEADLINE", label: "Deadline" },
          ]}
          value={prefs.jobSort}
          onChange={(jobSort) => set({ jobSort })}
        />
        <SegmentRow
          title="Match score"
          options={[
            { value: "ring", label: "Ring" },
            { value: "badge", label: "Badge" },
            { value: "hidden", label: "Hidden" },
          ]}
          value={prefs.scoreStyle}
          onChange={(scoreStyle) => set({ scoreStyle })}
        />
        <SegmentRow
          title="Dates"
          options={[
            { value: "relative", label: "2h ago" },
            { value: "absolute", label: "30 Sep" },
          ]}
          value={prefs.dateStyle}
          onChange={(dateStyle) => set({ dateStyle })}
          width={170}
        />
      </Group>

      <Group header="Job cards">
        <SwitchRow title="Why It Matches" subtitle="Show the top strength and gap on each card." value={prefs.cardInsights} onChange={(cardInsights) => set({ cardInsights })} />
        <SwitchRow title="Salary" value={prefs.showSalary} onChange={(showSalary) => set({ showSalary })} />
        <SwitchRow title="Source" subtitle="Which board or feed the role came from." value={prefs.showSource} onChange={(showSource) => set({ showSource })} />
      </Group>

      <Group header="Filters" footer="Filters apply to the Jobs tab and the Today screen. The agent still tracks everything.">
        <SwitchRow title="Hide Ineligible Roles" value={prefs.hideIneligible} onChange={(hideIneligible) => set({ hideIneligible })} />
        <StepperRow
          title="Minimum match"
          value={prefs.minScore}
          min={0}
          max={90}
          step={5}
          format={(v) => (v === 0 ? "Off" : `${v}%`)}
          onChange={(minScore) => set({ minScore })}
        />
      </Group>

      <Group header="Job details">
        <SwitchRow title="Confirm Before Dismissing" value={prefs.confirmDismiss} onChange={(confirmDismiss) => set({ confirmDismiss })} />
        <SwitchRow title="Expand Descriptions" subtitle="Show the full job description by default." value={prefs.expandDescription} onChange={(expandDescription) => set({ expandDescription })} />
        <SegmentRow
          title="Open postings"
          options={[
            { value: "in-app", label: "In App" },
            { value: "browser", label: "Browser" },
          ]}
          value={prefs.openLinks}
          onChange={(openLinks) => set({ openLinks })}
          width={170}
        />
      </Group>
    </Screen>
  );
}
