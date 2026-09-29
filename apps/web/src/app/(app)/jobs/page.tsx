import type { Metadata } from "next";

import { EmptyState, PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Opportunities" };

export default function Page() {
  return (
    <>
      <PageHeader title="Opportunities" description="Jobs, internships and research roles your agent discovered and matched." />
      <EmptyState title="Nothing here yet" description="Add job sources in Settings and run discovery to fill your inbox." />
    </>
  );
}
