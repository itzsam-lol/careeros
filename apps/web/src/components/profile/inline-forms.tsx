"use client";

import { useMutation } from "@tanstack/react-query";
import { useEffect, useMemo } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";

import { FormFields, type FormValues, toFormValues, toPayload } from "@/components/profile/form-fields";
import { Button } from "@/components/ui/button";
import { ApiError, unwrap, useApi } from "@/lib/api";
import { titleCase } from "@/lib/format";
import { looseCall } from "@/lib/loose-api";
import { fieldErrors, useInvalidateProfile } from "@/lib/profile";
import { EMPLOYMENT_TYPES, type FieldDef } from "@/lib/profile-sections";

const opts = (values: readonly string[]) => values.map((value) => ({ value, label: titleCase(value) }));

export const BASICS_FIELDS: FieldDef[] = [
  { name: "full_name", label: "Full name", type: "text" },
  { name: "headline", label: "Headline", type: "text", placeholder: "ML engineer and researcher" },
  { name: "current_role", label: "Current role", type: "text" },
  { name: "location", label: "Location", type: "text", placeholder: "City, Country" },
  { name: "contact_email", label: "Contact email", type: "email" },
  { name: "phone", label: "Phone", type: "text" },
  { name: "linkedin_url", label: "LinkedIn", type: "url" },
  { name: "github_url", label: "GitHub", type: "url" },
  { name: "portfolio_url", label: "Portfolio", type: "url", wide: true },
  {
    name: "summary",
    label: "Professional summary",
    type: "textarea",
    wide: true,
    description: "Used as the basis for tailored resume summaries. Keep it factual.",
  },
  { name: "work_authorization", label: "Work authorization", type: "textarea", wide: true },
  { name: "authorized_countries", label: "Authorized to work in", type: "tags" },
  {
    name: "sponsorship_requirement",
    label: "Visa sponsorship",
    type: "select",
    options: [
      { value: "NOT_REQUIRED", label: "Not required" },
      { value: "REQUIRED", label: "Required (outside authorized countries)" },
      { value: "FUTURE", label: "Will be required in the future" },
      { value: "UNKNOWN", label: "Not sure" },
    ],
  },
  { name: "availability", label: "Availability", type: "textarea", wide: true },
  { name: "earliest_start_date", label: "Earliest start date", type: "date" },
];

export const PREFERENCE_FIELDS: FieldDef[] = [
  { name: "target_roles", label: "Target roles", type: "tags", wide: true },
  { name: "employment_types", label: "Employment types", type: "multiselect", wide: true, options: opts(EMPLOYMENT_TYPES) },
  { name: "target_countries", label: "Countries", type: "tags" },
  { name: "target_cities", label: "Cities", type: "tags" },
  {
    name: "remote_preference",
    label: "Work arrangement",
    type: "select",
    required: true,
    options: opts(["ANY", "REMOTE", "HYBRID", "ONSITE"]),
  },
  { name: "include_research", label: "Include research opportunities", type: "checkbox" },
  { name: "target_industries", label: "Industries", type: "tags", wide: true },
  { name: "target_technologies", label: "Technologies", type: "tags", wide: true },
  { name: "target_companies", label: "Dream companies", type: "tags", wide: true },
  { name: "excluded_companies", label: "Excluded companies", type: "tags", wide: true },
  {
    name: "excluded_keywords",
    label: "Exclude roles containing",
    type: "tags",
    wide: true,
    placeholder: "sales, unpaid",
  },
  { name: "min_compensation", label: "Minimum compensation", type: "number" },
  { name: "compensation_currency", label: "Currency", type: "text", placeholder: "INR" },
  {
    name: "compensation_period",
    label: "Per",
    type: "select",
    options: opts(["YEAR", "MONTH", "WEEK", "HOUR"]),
  },
  { name: "notes", label: "Notes for the agent", type: "textarea", wide: true },
];

export function InlineForm({
  fields,
  values,
  path,
  successMessage,
}: {
  fields: FieldDef[];
  values: Record<string, unknown>;
  path: "/api/v1/profile/basics" | "/api/v1/profile/preferences";
  successMessage: string;
}) {
  const api = useApi();
  const invalidate = useInvalidateProfile();
  const defaults = useMemo(() => toFormValues(fields, values), [fields, values]);
  const { reset, setError, handleSubmit, register, control, formState } = useForm<FormValues>({
    defaultValues: defaults,
  });

  useEffect(() => reset(defaults), [defaults, reset]);

  const mutation = useMutation({
    mutationFn: (form: FormValues) => {
      const body = toPayload(fields, form, null);
      if (typeof body.compensation_currency === "string") {
        body.compensation_currency = body.compensation_currency.toUpperCase();
      }
      return unwrap(looseCall(api, "PUT", path, body));
    },
    onSuccess: async () => {
      toast.success(successMessage);
      await invalidate();
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
    <form
      onSubmit={handleSubmit((form) => mutation.mutate(form))}
      className="glass grid gap-4 rounded-2xl p-5 sm:grid-cols-2"
    >
      <FormFields fields={fields} register={register} control={control} errors={formState.errors} />
      <div className="flex justify-end gap-2 sm:col-span-2">
        <Button type="button" variant="ghost" onClick={() => reset(defaults)} disabled={!formState.isDirty}>
          Reset
        </Button>
        <Button type="submit" disabled={mutation.isPending || !formState.isDirty}>
          {mutation.isPending ? "Saving…" : "Save changes"}
        </Button>
      </div>
    </form>
  );
}
