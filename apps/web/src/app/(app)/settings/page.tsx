import type { Metadata } from "next";

import { EmptyState, PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Settings" };

export default function Page() {
  return (
    <>
      <PageHeader title="Settings" description="Preferences, sources, integrations and limits." />
      <EmptyState title="Nothing here yet" description="Settings will appear here." />
    </>
  );
}
