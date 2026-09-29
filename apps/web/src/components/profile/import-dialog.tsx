"use client";

import { useMutation } from "@tanstack/react-query";
import { FileUp } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { ApiError, unwrap, useApi } from "@/lib/api";
import { looseCall } from "@/lib/loose-api";
import { useInvalidateProfile } from "@/lib/profile";

export function ImportDialog() {
  const api = useApi();
  const invalidate = useInvalidateProfile();
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [parseError, setParseError] = useState<string | null>(null);

  const mutation = useMutation({
    mutationFn: (payload: unknown) => unwrap(looseCall(api, "POST", "/api/v1/profile/import", payload)),
    onSuccess: async (result) => {
      const created = Object.values((result as { created: Record<string, number> }).created).reduce(
        (sum, n) => sum + n,
        0,
      );
      toast.success(`Imported ${created} items — review and verify them before the agent uses them.`);
      await invalidate();
      setOpen(false);
      setText("");
    },
    onError: (error) =>
      toast.error(error instanceof ApiError ? `Import failed: ${error.message}` : "Import failed"),
  });

  function submit() {
    try {
      const payload: unknown = JSON.parse(text);
      setParseError(null);
      mutation.mutate(payload);
    } catch {
      setParseError("That is not valid JSON.");
    }
  }

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline">
          <FileUp className="size-4" /> Import
        </Button>
      </DialogTrigger>
      <DialogContent className="glass-strong sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Import a structured profile</DialogTitle>
          <DialogDescription>
            Paste CareerOS profile JSON or choose a file. Imported items are marked as needing review
            and are never used until you verify them.
          </DialogDescription>
        </DialogHeader>
        <input
          type="file"
          accept="application/json,.json"
          className="text-sm file:mr-3 file:rounded-lg file:border-0 file:bg-foreground/5 file:px-3 file:py-1.5 file:text-sm"
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (file) setText(await file.text());
          }}
        />
        <Textarea
          rows={12}
          value={text}
          onChange={(event) => setText(event.target.value)}
          placeholder='{"basics": {...}, "projects": [...]}'
          className="font-mono text-xs"
          aria-invalid={parseError !== null}
        />
        {parseError ? <p className="text-sm text-destructive">{parseError}</p> : null}
        <DialogFooter>
          <Button variant="ghost" onClick={() => setOpen(false)}>
            Cancel
          </Button>
          <Button onClick={submit} disabled={!text.trim() || mutation.isPending}>
            {mutation.isPending ? "Importing…" : "Import"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
