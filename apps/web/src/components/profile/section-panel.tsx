"use client";

import { useMutation } from "@tanstack/react-query";
import { Check, Lock, MoreHorizontal, Pencil, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/page-header";
import { ItemFormDialog } from "@/components/profile/item-form-dialog";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { type Verification, VerificationBadge } from "@/components/verification-badge";
import { unwrap, useApi } from "@/lib/api";
import { looseCall } from "@/lib/loose-api";
import { useInvalidateProfile } from "@/lib/profile";
import type { SectionDef } from "@/lib/profile-sections";

type Item = Record<string, unknown> & { id: string; verification_status: Verification };

const STATUS_ACTIONS: { status: Verification; label: string }[] = [
  { status: "VERIFIED", label: "Mark verified" },
  { status: "UNVERIFIED", label: "Mark as needs review" },
  { status: "OUTDATED", label: "Mark outdated" },
  { status: "REJECTED", label: "Reject (never use)" },
];

function ItemCard({
  section,
  item,
  onEdit,
  onDelete,
}: {
  section: SectionDef;
  item: Item;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const api = useApi();
  const invalidate = useInvalidateProfile();
  const readOnly = section.readOnly?.(item) ?? null;
  const bullets = section.bullets?.(item) ?? [];
  const tags = section.tags?.(item) ?? [];
  const subtitle = section.subtitle?.(item);

  const setStatus = useMutation({
    mutationFn: (status: Verification) =>
      unwrap(looseCall(api, "POST", `/api/v1/profile/${section.key}/${item.id}/verification`, { status })),
    onSuccess: () => invalidate(),
    onError: (error) => toast.error(error.message),
  });

  return (
    <article className="glass group rounded-2xl p-4 transition-shadow hover:shadow-lg">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <h3 className="font-medium leading-snug">{section.title(item)}</h3>
          {subtitle ? <p className="text-sm text-muted-foreground">{subtitle}</p> : null}
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <VerificationBadge status={item.verification_status} />
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <Button variant="ghost" size="icon-sm" aria-label="Item actions">
                <MoreHorizontal className="size-4" />
              </Button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-52">
              {!readOnly ? (
                <DropdownMenuItem onSelect={onEdit}>
                  <Pencil className="size-4" /> Edit
                </DropdownMenuItem>
              ) : null}
              <DropdownMenuLabel className="text-xs text-muted-foreground">Trust level</DropdownMenuLabel>
              {STATUS_ACTIONS.filter((a) => a.status !== item.verification_status).map((action) => (
                <DropdownMenuItem key={action.status} onSelect={() => setStatus.mutate(action.status)}>
                  {action.label}
                </DropdownMenuItem>
              ))}
              {!readOnly ? (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem variant="destructive" onSelect={onDelete}>
                    <Trash2 className="size-4" /> Delete
                  </DropdownMenuItem>
                </>
              ) : null}
            </DropdownMenuContent>
          </DropdownMenu>
        </div>
      </div>

      {bullets.length > 0 ? (
        <ul className="mt-3 space-y-1.5 text-sm text-foreground/85">
          {bullets.slice(0, 4).map((bullet, index) => (
            <li key={index} className="flex gap-2">
              <span className="mt-2 size-1 shrink-0 rounded-full bg-primary/60" aria-hidden />
              <span>{bullet}</span>
            </li>
          ))}
          {bullets.length > 4 ? (
            <li className="pl-3 text-xs text-muted-foreground">+{bullets.length - 4} more</li>
          ) : null}
        </ul>
      ) : null}

      {tags.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {tags.map((tag) => (
            <span key={tag} className="rounded-full bg-foreground/5 px-2 py-0.5 text-xs text-foreground/75">
              {tag}
            </span>
          ))}
        </div>
      ) : null}

      {readOnly ? (
        <p className="mt-3 flex items-center gap-1.5 text-xs text-muted-foreground">
          <Lock className="size-3" aria-hidden /> {readOnly}
        </p>
      ) : null}

      {item.verification_status === "UNVERIFIED" ? (
        <div className="mt-3 flex items-center justify-between gap-3 rounded-xl bg-warning/10 px-3 py-2 text-sm">
          <span className="text-foreground/80">Imported — confirm it is accurate before the agent uses it.</span>
          <Button size="sm" onClick={() => setStatus.mutate("VERIFIED")} disabled={setStatus.isPending}>
            <Check className="size-3.5" /> Verify
          </Button>
        </div>
      ) : null}
    </article>
  );
}

export function SectionPanel({ section, items }: { section: SectionDef; items: Item[] }) {
  const api = useApi();
  const invalidate = useInvalidateProfile();
  const [editing, setEditing] = useState<Item | null>(null);
  const [creating, setCreating] = useState(false);
  const [deleting, setDeleting] = useState<Item | null>(null);
  const Icon = section.icon;
  const pending = items.filter((i) => i.verification_status === "UNVERIFIED");

  const remove = useMutation({
    mutationFn: (item: Item) => unwrap(looseCall(api, "DELETE", `/api/v1/profile/${section.key}/${item.id}`)),
    onSuccess: async () => {
      toast.success(`Deleted ${section.singular}`);
      await invalidate();
    },
    onError: (error) => toast.error(error.message),
  });

  const verifyAll = useMutation({
    mutationFn: () =>
      unwrap(
        api.POST("/api/v1/profile/verification", {
          body: { section: section.key, ids: pending.map((i) => i.id), status: "VERIFIED" },
        }),
      ),
    onSuccess: async (result) => {
      toast.success(`Verified ${result.updated} ${section.label.toLowerCase()}`);
      await invalidate();
    },
    onError: (error) => toast.error(error.message),
  });

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="space-y-1">
          <h2 className="flex items-center gap-2 text-lg font-semibold">
            <Icon className="size-5 text-primary" aria-hidden /> {section.label}
          </h2>
          <p className="text-sm text-muted-foreground">{section.description}</p>
        </div>
        <div className="flex gap-2">
          {pending.length > 1 ? (
            <Button variant="outline" onClick={() => verifyAll.mutate()} disabled={verifyAll.isPending}>
              <Check className="size-4" /> Verify all {pending.length}
            </Button>
          ) : null}
          <Button onClick={() => setCreating(true)}>
            <Plus className="size-4" /> Add {section.singular}
          </Button>
        </div>
      </div>

      {items.length === 0 ? (
        <EmptyState icon={Icon} title={`No ${section.label.toLowerCase()} yet`} description={section.description} />
      ) : (
        <div className="grid gap-3">
          {items.map((item) => (
            <ItemCard
              key={item.id}
              section={section}
              item={item}
              onEdit={() => setEditing(item)}
              onDelete={() => setDeleting(item)}
            />
          ))}
        </div>
      )}

      <ItemFormDialog
        section={section}
        item={editing}
        open={creating || editing !== null}
        onOpenChange={(open) => {
          if (!open) {
            setCreating(false);
            setEditing(null);
          }
        }}
      />

      <AlertDialog open={deleting !== null} onOpenChange={(open) => !open && setDeleting(null)}>
        <AlertDialogContent className="glass-strong">
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this {section.singular}?</AlertDialogTitle>
            <AlertDialogDescription>
              Facts derived from it will be removed and it will no longer be used in resumes or outreach.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              variant="destructive"
              onClick={() => {
                if (deleting) remove.mutate(deleting);
                setDeleting(null);
              }}
            >
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </section>
  );
}
