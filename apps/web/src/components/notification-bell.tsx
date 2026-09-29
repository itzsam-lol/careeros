"use client";

import { Bell, CheckCheck } from "lucide-react";
import type { Route } from "next";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { formatRelative } from "@/lib/format";
import { useMarkRead, useNotifications, useUnreadCount } from "@/lib/notifications";
import { cn } from "@/lib/utils";

export function NotificationBell() {
  const [open, setOpen] = useState(false);
  const unread = useUnreadCount();
  const list = useNotifications(open);
  const markRead = useMarkRead();
  const count = unread.data?.unread ?? 0;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button variant="ghost" size="icon-sm" className="relative" aria-label={`Notifications (${count} unread)`}>
          <Bell className="size-4" />
          {count > 0 ? (
            <span className="absolute -right-0.5 -top-0.5 flex min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold leading-4 text-primary-foreground">
              {count > 99 ? "99+" : count}
            </span>
          ) : null}
        </Button>
      </PopoverTrigger>
      <PopoverContent align="start" className="glass-strong w-[22rem] p-0">
        <div className="flex items-center justify-between border-b border-foreground/10 px-4 py-2.5">
          <p className="text-sm font-semibold">Notifications</p>
          <Button variant="ghost" size="xs" onClick={() => markRead.mutate(undefined)} disabled={count === 0}>
            <CheckCheck className="size-3.5" /> Mark all read
          </Button>
        </div>
        <ul className="max-h-[26rem] overflow-y-auto">
          {list.isPending ? <li className="px-4 py-6 text-sm text-muted-foreground">Loading…</li> : null}
          {list.data?.length === 0 ? (
            <li className="px-4 py-6 text-sm text-muted-foreground">You&apos;re all caught up.</li>
          ) : null}
          {list.data?.map((notification) => (
            <li key={notification.id}>
              <Link
                href={(notification.action_url ?? "/dashboard") as Route}
                onClick={() => {
                  setOpen(false);
                  if (!notification.read) markRead.mutate([notification.id]);
                }}
                className="flex gap-3 px-4 py-3 transition-colors hover:bg-foreground/5"
              >
                <span
                  className={cn("mt-1.5 size-2 shrink-0 rounded-full", notification.read ? "bg-transparent" : "bg-primary")}
                  aria-hidden
                />
                <span className="min-w-0 space-y-0.5">
                  <span className="line-clamp-2 block text-sm font-medium">{notification.title}</span>
                  {notification.body ? (
                    <span className="line-clamp-2 block text-xs text-muted-foreground">{notification.body}</span>
                  ) : null}
                  <span className="block text-[11px] text-muted-foreground">{formatRelative(notification.created_at)}</span>
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  );
}
