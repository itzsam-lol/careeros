import { useState } from "react";

import { Screen } from "@/components/screen";
import { SavingNote, TagEditor } from "@/components/settings-kit";
import { Button, Card, EmptyState, Group, Loading, Row, Segmented, StepperRow, SwitchRow } from "@/components/ui";
import { type Preferences, type Schema, useProfile, useUpdatePreferences } from "@/lib/api";
import { compactMoney } from "@/lib/format";

type ListField = "target_roles" | "target_technologies" | "target_companies" | "target_countries" | "target_cities" | "excluded_companies" | "excluded_keywords";

const LISTS: { field: ListField; header: string; placeholder: string; footer?: string }[] = [
  { field: "target_roles", header: "Target roles", placeholder: "e.g. ML engineer", footer: "Roles close to these titles score higher." },
  { field: "target_technologies", header: "Technologies", placeholder: "e.g. PyTorch" },
  { field: "target_companies", header: "Dream companies", placeholder: "e.g. DeepMind" },
  { field: "target_countries", header: "Countries", placeholder: "e.g. India", footer: "Roles elsewhere are marked ineligible unless remote." },
  { field: "target_cities", header: "Cities", placeholder: "e.g. Bengaluru" },
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
