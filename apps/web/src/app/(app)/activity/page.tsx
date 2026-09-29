import type { Metadata } from "next";

import { EmptyState, PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Agent activity" };

export default function Page() {
  return (
    <>
      <PageHeader title="Agent activity" description="What your career agent has been doing." />
      <EmptyState title="Nothing here yet" description="Activity appears once discovery runs." />
    </>
  );
}
