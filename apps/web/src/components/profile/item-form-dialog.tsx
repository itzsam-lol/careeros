"use client";

import { useMutation } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { FormFields, type FormValues, toFormValues, toPayload } from "@/components/profile/form-fields";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { ApiError, unwrap, useApi } from "@/lib/api";
import { looseCall } from "@/lib/loose-api";
import { fieldErrors, useInvalidateProfile } from "@/lib/profile";
import type { SectionDef } from "@/lib/profile-sections";

type Item = Record<string, unknown> & { id: string };

export function ItemFormDialog({
  section,
  item,
  open,
  onOpenChange,
}: {
  section: SectionDef;
  item: Item | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const api = useApi();
  const invalidate = useInvalidateProfile();
  const defaults = useMemo(() => toFormValues(section.fields, item), [section, item]);
  const { reset, setError, handleSubmit, register, control, formState } = useForm<FormValues>({
    defaultValues: defaults,
  });

  useEffect(() => {
    if (open) reset(defaults);
  }, [open, defaults, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) => {
      const body = toPayload(section.fields, values, item);
      const path = item ? `/api/v1/profile/${section.key}/${item.id}` : `/api/v1/profile/${section.key}`;
      return unwrap(looseCall(api, item ? "PUT" : "POST", path, body));
    },
    onSuccess: async () => {
      toast.success(item ? `Updated ${section.singular}` : `Added ${section.singular}`);
      await invalidate();
      onOpenChange(false);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 422) {
        const errors = fieldErrors(error.details);
        for (const [name, message] of Object.entries(errors)) setError(name, { message });
        if (Object.keys(errors).length === 0) toast.error(error.message);
        return;
      }
      toast.error(error instanceof Error ? error.message : "Something went wrong");
    },
  });

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="glass-strong max-h-[88vh] overflow-y-auto sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>{item ? `Edit ${section.singular}` : `Add ${section.singular}`}</DialogTitle>
          <DialogDescription>{section.description}</DialogDescription>
        </DialogHeader>
        <form
          id={`form-${section.key}`}
          onSubmit={handleSubmit((values) => mutation.mutate(values))}
          className="grid gap-4 sm:grid-cols-2"
        >
          <FormFields fields={section.fields} register={register} control={control} errors={formState.errors} />
        </form>
        <DialogFooter>
          <Button variant="ghost" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button type="submit" form={`form-${section.key}`} disabled={mutation.isPending}>
            {mutation.isPending ? "Saving…" : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
