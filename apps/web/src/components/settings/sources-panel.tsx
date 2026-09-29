"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Play, Plus, Rss, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { EmptyState } from "@/components/page-header";
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
import { Checkbox } from "@/components/ui/checkbox";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { ApiError, type Schema, unwrap, useApi } from "@/lib/api";
import { env } from "@/lib/env";
import { formatRelative, titleCase } from "@/lib/format";
import { cn } from "@/lib/utils";

type Source = Schema<"SourceOut">;
type SourceType = Schema<"SourceType">;
type Cadence = Schema<"DiscoveryCadence">;

interface ConfigField {
  name: string;
  label: string;
  placeholder?: string;
  help?: string;
  optional?: boolean;
  kind?: "text" | "checkbox" | "region";
}

const TYPES: { type: SourceType; label: string; description: string; fields: ConfigField[] }[] = [
  {
    type: "GREENHOUSE",
    label: "Greenhouse board",
    description: "Companies hiring through Greenhouse (boards.greenhouse.io/<token>).",
    fields: [
      { name: "board_token", label: "Board token", placeholder: "e.g. stripe", help: "The part after boards.greenhouse.io/" },
      { name: "company_name", label: "Company name", optional: true },
    ],
  },
  {
    type: "LEVER",
    label: "Lever board",
    description: "Companies hiring through Lever (jobs.lever.co/<company>).",
    fields: [
      { name: "company", label: "Company slug", placeholder: "e.g. netflix", help: "The part after jobs.lever.co/" },
      { name: "company_name", label: "Company name", optional: true },
      { name: "region", label: "Region", kind: "region", optional: true },
    ],
  },
  {
    type: "ASHBY",
    label: "Ashby board",
    description: "Companies hiring through Ashby (jobs.ashbyhq.com/<organization>).",
    fields: [
      { name: "organization", label: "Organization", placeholder: "e.g. linear" },
      { name: "company_name", label: "Company name", optional: true },
    ],
  },
  {
    type: "SMARTRECRUITERS",
    label: "SmartRecruiters",
    description: "Companies hiring through SmartRecruiters.",
    fields: [
      { name: "company", label: "Company identifier", placeholder: "e.g. BoschGroup" },
      { name: "company_name", label: "Company name", optional: true },
    ],
  },
  {
    type: "CAREER_PAGE",
    label: "Career page",
    description: "Any careers page that publishes machine-readable job postings (schema.org JobPosting).",
    fields: [
      { name: "url", label: "Page URL", placeholder: "https://company.com/careers" },
      { name: "company_name", label: "Company name", optional: true },
      { name: "follow_links", label: "Also check linked job pages", kind: "checkbox", optional: true },
    ],
  },
  {
    type: "RSS",
    label: "RSS / Atom feed",
    description: "Job feeds from boards, universities and labs.",
    fields: [
      { name: "url", label: "Feed URL", placeholder: "https://example.edu/jobs.rss" },
      { name: "company_name", label: "Organisation name", optional: true },
    ],
  },
  ...(env.authMode === "dev"
    ? [
        {
          type: "FIXTURE" as SourceType,
          label: "Demo feed (development)",
          description: "Synthetic postings from fixtures/jobs for local testing.",
          fields: [{ name: "name", label: "Fixture name", placeholder: "demo_feed" }],
        },
      ]
    : []),
];

const CADENCES: { value: Cadence; label: string }[] = [
  { value: "EVERY_15_MIN", label: "Every 15 minutes" },
  { value: "EVERY_30_MIN", label: "Every 30 minutes" },
  { value: "HOURLY", label: "Hourly" },
  { value: "EVERY_6_HOURS", label: "Every 6 hours" },
  { value: "DAILY", label: "Daily" },
  { value: "MANUAL", label: "Only when I run it" },
];

const HEALTH: Record<string, string> = {
  healthy: "bg-success/12 text-success ring-success/25",
  degraded: "bg-warning/15 text-foreground/80 ring-warning/30",
  failing: "bg-destructive/10 text-destructive ring-destructive/20",
  never_run: "bg-foreground/5 text-muted-foreground ring-foreground/10",
  disabled: "bg-foreground/5 text-muted-foreground ring-foreground/10",
};

function AddSourceDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (open: boolean) => void }) {
  const api = useApi();
  const queryClient = useQueryClient();
  const [type, setType] = useState<SourceType>("GREENHOUSE");
  const [name, setName] = useState("");
  const [cadence, setCadence] = useState<Cadence>("DAILY");
  const [config, setConfig] = useState<Record<string, string | boolean>>({});
  const definition = TYPES.find((t) => t.type === type) ?? TYPES[0]!;

  const create = useMutation({
    mutationFn: () => {
      const clean: Record<string, unknown> = {};
      for (const field of definition.fields) {
        const value = config[field.name];
        if (field.kind === "checkbox") {
          if (value) clean[field.name] = true;
        } else if (typeof value === "string" && value.trim()) {
          clean[field.name] = value.trim();
        }
      }
      const fallbackName = String(clean.company_name ?? clean.board_token ?? clean.company ?? clean.organization ?? clean.url ?? clean.name ?? type);
      return unwrap(
        api.POST("/api/v1/sources", {
          body: { name: name.trim() || fallbackName, type, config: clean, cadence, enabled: true },
        }),
      );
    },
    onSuccess: async () => {
      toast.success("Source added", { description: "The first discovery run has been queued." });
      await queryClient.invalidateQueries({ queryKey: ["sources"] });
      onOpenChange(false);
      setConfig({});
      setName("");
    },
    onError: (error) => {
      const reason = error instanceof ApiError ? (error.details.reason as string | undefined) : undefined;
      toast.error(error.message, { description: reason?.split("\n").slice(0, 3).join(" ") });
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="glass-strong max-h-[88vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>Add a job source</DialogTitle>
          <DialogDescription>
            CareerOS uses official job-board APIs and public feeds, respects robots.txt and never scrapes behind logins.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-2 sm:grid-cols-2">
          {TYPES.map((option) => (
            <button
              key={option.type}
              type="button"
              onClick={() => {
                setType(option.type);
                setConfig({});
              }}
              className={cn(
                "rounded-xl p-3 text-left ring-1 ring-inset transition-colors",
                type === option.type ? "bg-primary/10 ring-primary/40" : "ring-foreground/10 hover:bg-foreground/5",
              )}
            >
              <p className="text-sm font-medium">{option.label}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{option.description}</p>
            </button>
          ))}
        </div>
        <div className="grid gap-4">
          {definition.fields.map((field) =>
            field.kind === "checkbox" ? (
              <label key={field.name} className="flex items-center gap-2 text-sm">
                <Checkbox
                  checked={Boolean(config[field.name])}
                  onCheckedChange={(checked) => setConfig((c) => ({ ...c, [field.name]: checked === true }))}
                />
                {field.label}
              </label>
            ) : field.kind === "region" ? (
              <Field key={field.name}>
                <FieldLabel>{field.label}</FieldLabel>
                <Select value={String(config[field.name] || "global")} onValueChange={(v) => setConfig((c) => ({ ...c, [field.name]: v }))}>
                  <SelectTrigger className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="global">Global (api.lever.co)</SelectItem>
                    <SelectItem value="eu">EU (api.eu.lever.co)</SelectItem>
                  </SelectContent>
                </Select>
              </Field>
            ) : (
              <Field key={field.name}>
                <FieldLabel htmlFor={`source-${field.name}`}>
                  {field.label}
                  {field.optional ? <span className="text-xs font-normal text-muted-foreground">(optional)</span> : null}
                </FieldLabel>
                <Input
                  id={`source-${field.name}`}
                  value={String(config[field.name] ?? "")}
                  placeholder={field.placeholder}
                  onChange={(event) => setConfig((c) => ({ ...c, [field.name]: event.target.value }))}
                />
                {field.help ? <FieldDescription>{field.help}</FieldDescription> : null}
              </Field>
            ),
          )}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field>
              <FieldLabel htmlFor="source-name">Display name</FieldLabel>
              <Input id="source-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="Optional" />
            </Field>
            <Field>
              <FieldLabel>Check for new jobs</FieldLabel>
              <Select value={cadence} onValueChange={(v) => setCadence(v as Cadence)}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CADENCES.map((option) => (
                    <SelectItem key={option.value} value={option.value}>
                      {option.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </Field>
          </div>
        </div>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={() => create.mutate()} disabled={create.isPending}>
            {create.isPending ? "Adding…" : "Add source"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function SourceRow({ source }: { source: Source }) {
  const api = useApi();
  const queryClient = useQueryClient();
  const [confirm, setConfirm] = useState(false);
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["sources"] });
  const path = { params: { path: { source_id: source.id } } };

  const update = useMutation({
    mutationFn: (body: Schema<"SourceUpdate">) => unwrap(api.PATCH("/api/v1/sources/{source_id}", { ...path, body })),
    onSuccess: refresh,
    onError: (error) => toast.error(error.message),
  });
  const run = useMutation({
    mutationFn: () => unwrap(api.POST("/api/v1/sources/{source_id}/run", path)),
    onSuccess: () => {
      toast.success(`Running ${source.name}`, { description: "New matches will appear in your inbox." });
      setTimeout(() => void refresh(), 5000);
    },
    onError: (error) => toast.error(error.message),
  });
  const remove = useMutation({
    mutationFn: () => unwrap(api.DELETE("/api/v1/sources/{source_id}", path)),
    onSuccess: refresh,
  });

  return (
    <li className="glass rounded-2xl p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium">{source.name}</p>
            <span className={cn("rounded-full px-2 py-0.5 text-xs ring-1 ring-inset", HEALTH[source.health])}>
              {titleCase(source.health)}
            </span>
          </div>
          <p className="text-sm text-muted-foreground">
            {titleCase(source.type)} · {CADENCES.find((c) => c.value === source.cadence)?.label}
            {source.last_success_at ? ` · last run ${formatRelative(source.last_success_at)}` : ""}
            {source.run_count ? ` · ${source.last_jobs_found} jobs last time` : ""}
          </p>
          {source.last_error && source.consecutive_failures > 0 ? (
            <p className="text-sm text-destructive">{source.last_error}</p>
          ) : null}
        </div>
        <div className="flex items-center gap-2">
          <Switch
            checked={source.enabled}
            onCheckedChange={(enabled) => update.mutate({ enabled })}
            aria-label={source.enabled ? "Disable source" : "Enable source"}
          />
          <Select value={source.cadence} onValueChange={(v) => update.mutate({ cadence: v as Cadence })}>
            <SelectTrigger className="h-8 w-40" aria-label="Cadence">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {CADENCES.map((option) => (
                <SelectItem key={option.value} value={option.value}>
                  {option.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Button variant="outline" size="sm" onClick={() => run.mutate()} disabled={!source.enabled || run.isPending}>
            <Play className="size-3.5" /> Run
          </Button>
          <Button variant="ghost" size="icon-sm" aria-label="Delete source" onClick={() => setConfirm(true)}>
            <Trash2 className="size-4" />
          </Button>
        </div>
      </div>
      <AlertDialog open={confirm} onOpenChange={setConfirm}>
        <AlertDialogContent className="glass-strong">
          <AlertDialogHeader>
            <AlertDialogTitle>Remove {source.name}?</AlertDialogTitle>
            <AlertDialogDescription>
              Discovery from this source stops. Jobs already in your inbox stay there.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction variant="destructive" onClick={() => remove.mutate()}>
              Remove
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </li>
  );
}

export function SourcesPanel() {
  const api = useApi();
  const [adding, setAdding] = useState(false);
  const sources = useQuery({
    queryKey: ["sources"],
    queryFn: () => unwrap(api.GET("/api/v1/sources")),
    refetchInterval: 30_000,
  });

  return (
    <section className="space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold">Job sources</h2>
          <p className="text-sm text-muted-foreground">Where your agent looks for opportunities, and how often.</p>
        </div>
        <Button onClick={() => setAdding(true)}>
          <Plus className="size-4" /> Add source
        </Button>
      </div>
      {sources.isPending ? null : sources.data && sources.data.length > 0 ? (
        <ul className="space-y-3">
          {sources.data.map((source) => (
            <SourceRow key={source.id} source={source} />
          ))}
        </ul>
      ) : (
        <EmptyState
          icon={Rss}
          title="No sources yet"
          description="Add the job boards of companies you care about. Greenhouse, Lever and Ashby boards work out of the box."
          action={<Button onClick={() => setAdding(true)}>Add your first source</Button>}
        />
      )}
      <AddSourceDialog open={adding} onOpenChange={setAdding} />
    </section>
  );
}
