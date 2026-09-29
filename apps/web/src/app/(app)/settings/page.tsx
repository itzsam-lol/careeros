"use client";

import { PageHeader } from "@/components/page-header";
import { AccountPanel } from "@/components/settings/account-panel";
import { MatchingPanel } from "@/components/settings/matching-panel";
import { SourcesPanel } from "@/components/settings/sources-panel";

export default function SettingsPage() {
  return (
    <>
      <PageHeader title="Settings" description="Sources, matching thresholds, notifications and your account." />
      <div className="space-y-10">
        <SourcesPanel />
        <MatchingPanel />
        <AccountPanel />
      </div>
    </>
  );
}
