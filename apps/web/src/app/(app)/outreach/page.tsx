import type { Metadata } from "next";

import { EmptyState, PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Outreach" };

export default function Page() {
  return (
    <>
      <PageHeader title="Outreach" description="Personalised emails that wait for your approval before sending." />
      <EmptyState title="Nothing here yet" description="Draft outreach from an opportunity's contacts." />
    </>
  );
}
