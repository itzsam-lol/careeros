"use client";

import { useQuery } from "@tanstack/react-query";

import { PageHeader } from "@/components/page-header";
import { Skeleton } from "@/components/ui/skeleton";
import { unwrap, useApi } from "@/lib/api";

export default function DashboardPage() {
  const api = useApi();
  const me = useQuery({ queryKey: ["me"], queryFn: () => unwrap(api.GET("/api/v1/me")) });

  return (
    <>
      <PageHeader
        title={me.data ? `Welcome back${me.data.name ? `, ${me.data.name}` : ""}` : "Dashboard"}
        description="Your career agent's view of new opportunities, applications and outreach."
      />
      {me.isPending ? <Skeleton className="h-32 w-full" /> : null}
      {me.isError ? (
        <p className="text-sm text-destructive">Could not reach the CareerOS API.</p>
      ) : null}
    </>
  );
}
