"use client";

import {
  Activity,
  BriefcaseBusiness,
  ClipboardCheck,
  FileText,
  LayoutDashboard,
  LogOut,
  Menu,
  Send,
  Settings,
  Sparkles,
  UserRound,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { useAuth } from "@/lib/auth";
import { cn } from "@/lib/utils";

export const NAV_ITEMS = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/jobs", label: "Opportunities", icon: BriefcaseBusiness },
  { href: "/applications", label: "Applications", icon: ClipboardCheck },
  { href: "/outreach", label: "Outreach", icon: Send },
  { href: "/resumes", label: "Resumes", icon: FileText },
  { href: "/profile", label: "Profile", icon: UserRound },
  { href: "/activity", label: "Agent activity", icon: Activity },
  { href: "/settings", label: "Settings", icon: Settings },
] as const;

function NavLinks({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-0.5">
      {NAV_ITEMS.map(({ href, label, icon: Icon }) => {
        const active = pathname === href || pathname.startsWith(`${href}/`);
        return (
          <Link
            key={href}
            href={href}
            onClick={onNavigate}
            className={cn(
              "flex items-center gap-2.5 rounded-xl px-3 py-2 text-sm font-medium transition-colors",
              active
                ? "bg-primary/10 text-primary shadow-[inset_0_0_0_1px] shadow-primary/15"
                : "text-muted-foreground hover:bg-foreground/5 hover:text-foreground",
            )}
          >
            <Icon className="size-4" aria-hidden />
            {label}
          </Link>
        );
      })}
    </nav>
  );
}

function Brand() {
  return (
    <Link href="/dashboard" className="flex items-center gap-2 px-2.5 py-1">
      <span className="flex size-8 items-center justify-center rounded-xl bg-gradient-to-br from-primary to-[oklch(0.62_0.17_300)] text-primary-foreground shadow-md shadow-primary/30">
        <Sparkles className="size-4" aria-hidden />
      </span>
      <span className="text-base font-semibold tracking-tight">CareerOS</span>
    </Link>
  );
}

function UserFooter() {
  const { user, signOut, mode } = useAuth();
  return (
    <div className="flex items-center justify-between gap-2 border-t border-foreground/10 px-2.5 pt-3">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{user?.name ?? "Signed in"}</p>
        <p className="truncate text-xs text-muted-foreground">
          {user?.email}
          {mode === "dev" ? " · dev" : ""}
        </p>
      </div>
      <div className="flex items-center gap-0.5">
        <ThemeToggle />
        {mode === "firebase" ? (
          <Button variant="ghost" size="icon-sm" onClick={() => void signOut()} aria-label="Sign out">
            <LogOut className="size-4" />
          </Button>
        ) : null}
      </div>
    </div>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  return (
    <div className="relative flex min-h-screen">
      <div aria-hidden className="app-backdrop fixed inset-0 -z-10" />

      <aside className="sticky top-0 hidden h-screen w-64 shrink-0 p-3 md:block">
        <div className="glass-strong flex h-full flex-col gap-5 rounded-2xl p-3">
          <Brand />
          <div className="flex-1 overflow-y-auto">
            <NavLinks />
          </div>
          <UserFooter />
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="glass-strong sticky top-0 z-30 flex items-center gap-2 rounded-none border-x-0 border-t-0 px-3 py-2 md:hidden">
          <Sheet open={open} onOpenChange={setOpen}>
            <SheetTrigger asChild>
              <Button variant="ghost" size="icon" aria-label="Open navigation">
                <Menu className="size-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="left" className="glass-strong flex w-72 flex-col gap-5 border-0 p-3">
              <SheetTitle className="sr-only">Navigation</SheetTitle>
              <Brand />
              <div className="flex-1">
                <NavLinks onNavigate={() => setOpen(false)} />
              </div>
              <UserFooter />
            </SheetContent>
          </Sheet>
          <Brand />
        </header>
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-6 md:px-8 md:py-8">{children}</main>
      </div>
    </div>
  );
}
