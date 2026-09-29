import type { Metadata } from "next";

import { EmptyState, PageHeader } from "@/components/page-header";

export const metadata: Metadata = { title: "Resumes" };

export default function Page() {
  return (
    <>
      <PageHeader title="Resumes" description="Tailored, evidence-grounded resume versions." />
      <EmptyState title="Nothing here yet" description="Generate a resume from any opportunity." />
    </>
  );
}
