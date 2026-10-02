import { useState } from "react";

import { Screen } from "@/components/screen";
import { SavingNote, TagEditor } from "@/components/settings-kit";
import { Button, Card, EmptyState, Group, Loading, Row, Segmented, StepperRow, SwitchRow } from "@/components/ui";
import { type Preferences, type Schema, useProfile, useUpdatePreferences } from "@/lib/api";
import { compactMoney } from "@/lib/format";

type ListField =
  | "target_roles"
  | "target_technologies"
  | "target_companies"
  | "target_countries"
  | "target_cities"
  | "sponsorship_required_countries"
  | "excluded_companies"
  | "excluded_keywords";

const LISTS: { field: ListField; header: string; placeholder: string; footer?: string }[] = [
  { field: "target_roles", header: "Target roles", placeholder: "e.g. ML engineer", footer: "Roles close to these titles score higher." },
  { field: "target_technologies", header: "Technologies", placeholder: "e.g. PyTorch" },
  {
    field: "target_companies",
    header: "Dream companies",
    placeholder: "e.g. NatWest",
    footer: "Every fresher role you're eligible for here gets a tailored résumé and cover letter, and a Ready to Apply alert, whatever its match score.",
  },
  { field: "target_countries", header: "Countries", placeholder: "e.g. India", footer: "Roles elsewhere are marked ineligible unless remote." },
  { field: "target_cities", header: "Cities", placeholder: "e.g. Bengaluru" },
  {
    field: "sponsorship_required_countries",
    header: "Only with visa sponsorship",
    placeholder: "e.g. Australia",
    footer: "Roles in these countries are hidden unless the posting explicitly offers visa sponsorship.",
  },
  { field: "excluded_companies", header: "Never show companies", placeholder: "Company name", footer: "Roles from these companies are skipped entirely." },
  { field: "excluded_keywords", header: "Never show keywords", placeholder: "e.g. unpaid", footer: "Postings containing these words are skipped." },
];

export default function SearchSettingsScreen() {
  const profile = useProfile();
  const update = useUpdatePreferences();
  const [pending, setPending] = useState<Partial<Preferences>>({});
  const saved = profile.data?.preferences;
  // Show edits immediately; the server copy replaces them once it is refetched.
  const prefs = saved ? { ...saved, ...pending } : undefined;

  const save = (patch: Schema<"PreferencesIn">) => {
    setPending((current) => ({ ...current, ...(patch as Partial<Preferences>) }));
    update.mutate(patch, { onSettled: () => setPending({}) });
  };

  return (
    <Screen title="Job Search" back="Settings" backFallback="/settings" tabBar={false} subtitle="Used by the agent for discovery, eligibility and scoring. Existing matches are re-scored within a few minutes.">
      {profile.isPending ? (
        <Loading />
      ) : profile.isError || !prefs ? (
        <Card>
          <EmptyState
            icon="cloud-offline-outline"
            title="Couldn't load preferences"
            message={profile.error?.message}
            action={<Button label="Try Again" variant="tinted" size="medium" onPress={() => void profile.refetch()} />}
          />
        </Card>
      ) : (
        <>
          <Group
            header="Your feed"
            footer="Hidden roles stay out of your lists and alerts; you can still find them under Dismissed."
          >
            <SwitchRow
              title="Freshers Only"
              subtitle="Internships, graduate and entry-level roles. Mid and senior roles, or roles asking for more than 2 years, are skipped."
              value={prefs.entry_level_only}
              onChange={(entry_level_only) => save({ entry_level_only })}
            />
            <SwitchRow
              title="Hide Roles That Don't Fit"
              subtitle="Roles you aren't eligible for, or a different kind of work from your target roles."
              value={prefs.hide_unsuitable}
              onChange={(hide_unsuitable) => save({ hide_unsuitable })}
            />
          </Group>

          <Group header="Work style">
            <Row
              title="Location"
              below={<Segmented
                    options={[
                      { value: "ANY", label: "Any" },
                      { value: "REMOTE", label: "Remote" },
                      { value: "HYBRID", label: "Hybrid" },
                      { value: "ONSITE", label: "On-site" },
                    ]}
                    value={prefs.remote_preference}
                    onChange={(remote_preference) => save({ remote_preference })}
                  />}
            />
            <SwitchRow
              title="Include Research Roles"
              subtitle="Research assistant and lab positions."
              value={prefs.include_research}
              onChange={(include_research) => save({ include_research })}
            />
            <StepperRow
              title="Minimum pay"
              subtitle={prefs.compensation_currency ? `Per ${prefs.compensation_period?.toLowerCase() ?? "year"}, ${prefs.compensation_currency}` : "Roles that list lower pay score lower."}
              value={prefs.min_compensation ?? 0}
              min={0}
              max={10_000_000}
              step={prefs.compensation_period === "MONTH" ? 5_000 : 100_000}
              format={(v) => (v === 0 ? "Any" : compactMoney(v))}
              onChange={(v) => save({ min_compensation: v === 0 ? null : v })}
            />
          </Group>

          {LISTS.map((list) => (
            <TagEditor
              key={list.field}
              header={list.header}
              footer={list.footer}
              placeholder={list.placeholder}
              values={prefs[list.field]}
              onChange={(next) => save({ [list.field]: next })}
            />
          ))}
          <SavingNote saving={update.isPending} error={update.error} />
        </>
      )}
    </Screen>
  );
}
