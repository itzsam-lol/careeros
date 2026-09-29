"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { type Schema, unwrap, useApi } from "@/lib/api";

type Settings = Schema<"UserSettings">;

function Percent({
  id,
  label,
  help,
  value,
  onChange,
}: {
  id: string;
  label: string;
  help: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <Field>
      <div className="flex items-center justify-between">
        <FieldLabel htmlFor={id}>{label}</FieldLabel>
        <span className="text-sm font-semibold tabular-nums">{Math.round(value * 100)}%</span>
      </div>
      <input
        id={id}
        type="range"
        min={30}
        max={95}
        step={5}
        value={Math.round(value * 100)}
        onChange={(event) => onChange(Number(event.target.value) / 100)}
        className="w-full accent-[var(--primary)]"
      />
      <FieldDescription>{help}</FieldDescription>
    </Field>
  );
}

export function MatchingPanel() {
  const api = useApi();
  const queryClient = useQueryClient();
  const settings = useQuery({ queryKey: ["settings"], queryFn: () => unwrap(api.GET("/api/v1/me/settings")) });
  // Local edits only; until the user changes something the form shows the server's values.
  const [edits, setDraft] = useState<Settings | null>(null);
  const draft = edits ?? settings.data ?? null;

  const save = useMutation({
    mutationFn: (value: Settings) =>
      unwrap(
        api.PATCH("/api/v1/me/settings", {
          body: { matching: value.matching, notifications: value.notifications },
        }),
      ),
    onSuccess: (value) => {
      queryClient.setQueryData(["settings"], value);
      setDraft(null);
      void queryClient.invalidateQueries({ queryKey: ["jobs"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Saved");
    },
    onError: (error) => toast.error(error.message),
  });

  if (!draft) return null;
  const matching = draft.matching ?? { high_match_threshold: 0.75, notify_threshold: 0.55 };
  const notifications = draft.notifications ?? { notify_new_jobs: true, deadline_warning_hours: 72 };

  return (
    <section className="space-y-4">
      <div>
        <h2 className="text-lg font-semibold">Matching & notifications</h2>
        <p className="text-sm text-muted-foreground">When a role counts as a high match, and when the agent should tell you.</p>
      </div>
      <div className="glass grid gap-6 rounded-2xl p-5 md:grid-cols-2">
        <Percent
          id="high"
          label="High match threshold"
          help="Eligible roles at or above this relevance are flagged as high matches."
          value={matching.high_match_threshold ?? 0.75}
          onChange={(v) => setDraft({ ...draft, matching: { ...matching, high_match_threshold: v } })}
        />
        <Percent
          id="notify"
          label="Notify me from"
          help="Eligible roles at or above this relevance create a notification."
          value={matching.notify_threshold ?? 0.55}
          onChange={(v) => setDraft({ ...draft, matching: { ...matching, notify_threshold: v } })}
        />
        <label className="flex items-center justify-between gap-4 text-sm">
          <span>
            <span className="block font-medium">New match notifications</span>
            <span className="text-muted-foreground">High matches always notify you.</span>
          </span>
          <Switch
            checked={notifications.notify_new_jobs ?? true}
            onCheckedChange={(v) => setDraft({ ...draft, notifications: { ...notifications, notify_new_jobs: v } })}
          />
        </label>
        <Field>
          <FieldLabel htmlFor="deadline-hours">Deadline warning (hours before)</FieldLabel>
          <Input
            id="deadline-hours"
            type="number"
            min={1}
            max={720}
            value={notifications.deadline_warning_hours ?? 72}
            onChange={(e) =>
              setDraft({ ...draft, notifications: { ...notifications, deadline_warning_hours: Number(e.target.value) || 72 } })
            }
          />
        </Field>
        <div className="flex justify-end md:col-span-2">
          <Button onClick={() => save.mutate(draft)} disabled={save.isPending}>
            {save.isPending ? "Saving…" : "Save settings"}
          </Button>
        </div>
      </div>
    </section>
  );
}
