import type { Metadata } from "next";

import { EmptyState, PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Applications" };

export default function Page() {
  return (
    <>
      <PageHeader title="Applications" description="Every application from first draft to offer." />
      <EmptyState title="Nothing here yet" description="Start an application from any opportunity." />
    </>
  );
}
