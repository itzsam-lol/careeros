"use client";

import { Controller, type Control, type FieldErrors, type UseFormRegister } from "react-hook-form";

import { Checkbox } from "@/components/ui/checkbox";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { fromMonthInput, toMonthInput } from "@/lib/format";
import type { FieldDef } from "@/lib/profile-sections";
import { cn } from "@/lib/utils";

export type FormValues = Record<string, string | boolean>;

const NONE = "__none__";
// Fields the API expects on update that forms do not edit: keep their current values.
const PRESERVED = ["sort_order", "publication_ids", "confidence", "valid_from", "valid_until"];

export function toFormValues(fields: FieldDef[], item: Record<string, unknown> | null): FormValues {
  const values: FormValues = {};
  for (const field of fields) {
    const raw = item?.[field.name];
    switch (field.type) {
      case "checkbox":
        values[field.name] = Boolean(raw);
        break;
      case "lines":
        values[field.name] = Array.isArray(raw) ? raw.join("\n") : "";
        break;
      case "tags":
        values[field.name] = Array.isArray(raw) ? raw.join(", ") : "";
        break;
      case "multiselect":
        values[field.name] = Array.isArray(raw) ? raw.join(",") : "";
        break;
      case "month":
        values[field.name] = toMonthInput(raw);
        break;
      case "select":
        values[field.name] = typeof raw === "string" ? raw : NONE;
        break;
      default:
        values[field.name] = raw === null || raw === undefined ? "" : String(raw);
    }
  }
  return values;
}

export function toPayload(
  fields: FieldDef[],
  values: FormValues,
  item: Record<string, unknown> | null,
): Record<string, unknown> {
  const payload: Record<string, unknown> = {};
  for (const key of PRESERVED) {
    if (item && key in item && item[key] !== undefined) payload[key] = item[key];
  }
  for (const field of fields) {
    const raw = values[field.name];
    const text = typeof raw === "string" ? raw.trim() : "";
    switch (field.type) {
      case "checkbox":
        payload[field.name] = Boolean(raw);
        break;
      case "lines":
        payload[field.name] = text.split("\n").map((s) => s.trim()).filter(Boolean);
        break;
      case "tags":
      case "multiselect":
        payload[field.name] = text.split(",").map((s) => s.trim()).filter(Boolean);
        break;
      case "month":
        payload[field.name] = fromMonthInput(text);
        break;
      case "number":
        payload[field.name] = text === "" ? null : Number(text);
        break;
      case "select":
        if (text && text !== NONE) payload[field.name] = text;
        else if (!field.required) payload[field.name] = null;
        break;
      default:
        payload[field.name] = text === "" ? null : text;
    }
  }
  return payload;
}

function FieldInput({
  field,
  register,
  control,
}: {
  field: FieldDef;
  register: UseFormRegister<FormValues>;
  control: Control<FormValues>;
}) {
  const id = `field-${field.name}`;
  const rules = field.required ? { required: `${field.label} is required` } : {};
  switch (field.type) {
    case "textarea":
    case "lines":
      return (
        <Textarea
          id={id}
          rows={field.type === "lines" ? 4 : 3}
          placeholder={field.placeholder}
          {...register(field.name, rules)}
        />
      );
    case "checkbox":
      return (
        <Controller
          name={field.name}
          control={control}
          render={({ field: f }) => (
            <label htmlFor={id} className="flex items-center gap-2 text-sm">
              <Checkbox id={id} checked={Boolean(f.value)} onCheckedChange={(v) => f.onChange(v === true)} />
              {field.label}
            </label>
          )}
        />
      );
    case "multiselect":
      return (
        <Controller
          name={field.name}
          control={control}
          render={({ field: f }) => {
            const selected = new Set(String(f.value || "").split(",").filter(Boolean));
            return (
              <div className="flex flex-wrap gap-1.5" role="group" aria-labelledby={`${id}-label`}>
                {field.options?.map((option) => {
                  const active = selected.has(option.value);
                  return (
                    <button
                      key={option.value}
                      type="button"
                      aria-pressed={active}
                      onClick={() => {
                        const next = new Set(selected);
                        if (active) next.delete(option.value);
                        else next.add(option.value);
                        f.onChange([...next].join(","));
                      }}
                      className={cn(
                        "rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset transition-colors",
                        active
                          ? "bg-primary text-primary-foreground ring-primary"
                          : "bg-foreground/5 text-foreground/80 ring-foreground/10 hover:bg-foreground/10",
                      )}
                    >
                      {option.label}
                    </button>
                  );
                })}
              </div>
            );
          }}
        />
      );
    case "select":
      return (
        <Controller
          name={field.name}
          control={control}
          rules={rules}
          render={({ field: f }) => (
            <Select value={String(f.value || NONE)} onValueChange={f.onChange}>
              <SelectTrigger id={id} className="w-full">
                <SelectValue placeholder="Select…" />
              </SelectTrigger>
              <SelectContent>
                {!field.required ? <SelectItem value={NONE}>Not specified</SelectItem> : null}
                {field.options?.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        />
      );
    default: {
      const types: Partial<Record<FieldDef["type"], string>> = {
        month: "month",
        date: "date",
        number: "number",
        url: "url",
        email: "email",
      };
      return (
        <Input
          id={id}
          type={types[field.type] ?? "text"}
          step={field.type === "number" ? "any" : undefined}
          placeholder={field.placeholder ?? (field.type === "tags" ? "Comma separated" : undefined)}
          {...register(field.name, rules)}
        />
      );
    }
  }
}

export function FormFields({
  fields,
  register,
  control,
  errors,
}: {
  fields: FieldDef[];
  register: UseFormRegister<FormValues>;
  control: Control<FormValues>;
  errors: FieldErrors<FormValues>;
}) {
  return (
    <>
      {fields.map((field) => (
        <Field key={field.name} className={cn(field.wide && "sm:col-span-2")}>
          {field.type !== "checkbox" ? (
            <FieldLabel id={`field-${field.name}-label`} htmlFor={`field-${field.name}`}>
              {field.label}
              {field.required ? <span className="text-destructive">*</span> : null}
            </FieldLabel>
          ) : null}
          <FieldInput field={field} register={register} control={control} />
          {field.description ? <FieldDescription>{field.description}</FieldDescription> : null}
          <FieldError errors={[errors[field.name]]} />
        </Field>
      ))}
    </>
  );
}
