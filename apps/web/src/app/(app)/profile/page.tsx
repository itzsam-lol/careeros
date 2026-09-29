import type { Metadata } from "next";

import { EmptyState, PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Profile" };

export default function Page() {
  return (
    <>
      <PageHeader title="Profile" description="Your verified professional knowledge base." />
      <EmptyState title="Nothing here yet" description="Build your profile to unlock matching." />
    </>
  );
}
