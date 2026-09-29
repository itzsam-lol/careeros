"use client";

import { useMutation } from "@tanstack/react-query";
import { RefreshCw, SlidersHorizontal, UserRound } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/page-header";
import { CompletenessCard } from "@/components/profile/completeness-card";
import { ImportDialog } from "@/components/profile/import-dialog";
import { BASICS_FIELDS, InlineForm, PREFERENCE_FIELDS } from "@/components/profile/inline-forms";
import { SectionPanel } from "@/components/profile/section-panel";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { unwrap, useApi } from "@/lib/api";
import { useProfile } from "@/lib/profile";
import { SECTIONS, type SectionKey } from "@/lib/profile-sections";
import { cn } from "@/lib/utils";

type Tab = "basics" | "preferences" | SectionKey;

const NAV: { key: Tab; label: string; icon: React.ComponentType<{ className?: string }> }[] = [
  { key: "basics", label: "Basics", icon: UserRound },
  { key: "preferences", label: "Preferences", icon: SlidersHorizontal },
  ...SECTIONS.map((section) => ({ key: section.key, label: section.label, icon: section.icon })),
];

export default function ProfilePage() {
  const api = useApi();
  const profile = useProfile();
  const [tab, setTab] = useState<Tab>("basics");

  const reindex = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/evidence/reindex")),
    onSuccess: (result) =>
      toast.success(
        result.embedded > 0
          ? `Refreshed ${result.embedded} evidence documents`
          : "Evidence index is already up to date",
      ),
    onError: (error) => toast.error(error.message),
  });

  if (profile.isPending) {
    return (
      <div className="space-y-4">
        <Skeleton className="h-10 w-48" />
        <Skeleton className="h-64 w-full rounded-2xl" />
      </div>
    );
  }
  if (profile.isError) {
    return <p className="text-sm text-destructive">Could not load your profile: {profile.error.message}</p>;
  }

  const data = profile.data;
  const counts: Partial<Record<Tab, number>> = Object.fromEntries(
    SECTIONS.map((s) => [s.key, (data[s.key] as unknown[]).length]),
  );
  const pending: Partial<Record<Tab, number>> = Object.fromEntries(
    SECTIONS.map((s) => [
      s.key,
      (data[s.key] as { verification_status: string }[]).filter((i) => i.verification_status === "UNVERIFIED")
        .length,
    ]),
  );
  const active = SECTIONS.find((s) => s.key === tab);

  return (
    <>
      <PageHeader
        title="Profile"
        description="Your verified professional knowledge base. The agent only uses what you have verified."
        actions={
          <>
            <ImportDialog />
            <Button variant="outline" onClick={() => reindex.mutate()} disabled={reindex.isPending}>
              <RefreshCw className={cn("size-4", reindex.isPending && "animate-spin")} /> Refresh evidence
            </Button>
          </>
        }
      />

      <div className="grid gap-6 lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="space-y-4 lg:sticky lg:top-8 lg:self-start">
          <CompletenessCard stats={data.stats} />
          <nav
            aria-label="Profile sections"
            className="glass flex gap-1 overflow-x-auto rounded-2xl p-2 lg:flex-col lg:overflow-visible"
          >
            {NAV.map(({ key, label, icon: Icon }) => (
              <button
                key={key}
                type="button"
                onClick={() => setTab(key)}
                aria-current={tab === key ? "page" : undefined}
                className={cn(
                  "flex shrink-0 items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
                  tab === key
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:bg-foreground/5 hover:text-foreground",
                )}
              >
                <Icon className="size-4" />
                <span className="flex-1 text-left">{label}</span>
                {pending[key] ? (
                  <span className="rounded-full bg-warning/20 px-1.5 text-xs font-semibold text-foreground/80">
                    {pending[key]}
                  </span>
                ) : counts[key] ? (
                  <span className="text-xs text-muted-foreground">{counts[key]}</span>
                ) : null}
              </button>
            ))}
          </nav>
        </aside>

        <div className="min-w-0">
          {tab === "basics" ? (
            <section className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold">Basics</h2>
                <p className="text-sm text-muted-foreground">
                  Identity, contact details and work authorization used across applications.
                </p>
              </div>
              <InlineForm
                fields={BASICS_FIELDS}
                values={data.basics}
                path="/api/v1/profile/basics"
                successMessage="Saved your basics"
              />
            </section>
          ) : null}
          {tab === "preferences" ? (
            <section className="space-y-4">
              <div>
                <h2 className="text-lg font-semibold">Career preferences</h2>
                <p className="text-sm text-muted-foreground">
                  What the agent should look for — and what it should never show you.
                </p>
              </div>
              <InlineForm
                fields={PREFERENCE_FIELDS}
                values={data.preferences}
                path="/api/v1/profile/preferences"
                successMessage="Saved your preferences"
              />
            </section>
          ) : null}
          {active ? (
            <SectionPanel
              key={active.key}
              section={active}
              items={data[active.key] as Parameters<typeof SectionPanel>[0]["items"]}
            />
          ) : null}
        </div>
      </div>
    </>
  );
}
