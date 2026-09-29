import type { Schema } from "@careeros/api-client";
import {
  Award,
  BookOpen,
  Briefcase,
  FlaskConical,
  FolderGit2,
  GraduationCap,
  type LucideIcon,
  MessageSquareQuote,
  Quote,
  Wrench,
} from "lucide-react";

import { formatMonth, formatPeriod, titleCase } from "@/lib/format";

export type SectionKey =
  | "education"
  | "experience"
  | "projects"
  | "research"
  | "publications"
  | "skills"
  | "achievements"
  | "facts"
  | "answers";

export type FieldType =
  | "text"
  | "textarea"
  | "month"
  | "date"
  | "checkbox"
  | "select"
  | "lines"
  | "tags"
  | "number"
  | "url"
  | "email"
  | "multiselect";

export interface FieldDef {
  name: string;
  label: string;
  type: FieldType;
  required?: boolean;
  placeholder?: string;
  description?: string;
  options?: { value: string; label: string }[];
  wide?: boolean;
}

type Item = Record<string, unknown> & {
  id: string;
  verification_status: "VERIFIED" | "UNVERIFIED" | "OUTDATED" | "REJECTED";
};

export interface SectionDef {
  key: SectionKey;
  label: string;
  singular: string;
  icon: LucideIcon;
  description: string;
  fields: FieldDef[];
  title: (item: Item) => string;
  subtitle?: (item: Item) => string | null;
  bullets?: (item: Item) => string[];
  tags?: (item: Item) => string[];
  readOnly?: (item: Item) => string | null;
}

const options = (values: readonly string[]) => values.map((value) => ({ value, label: titleCase(value) }));

const str = (value: unknown) => (typeof value === "string" ? value : "");
const list = (value: unknown) => (Array.isArray(value) ? value.map(String) : []);
const join = (...parts: (string | null | undefined)[]) => parts.filter(Boolean).join(" · ") || null;

export const EMPLOYMENT_TYPES = [
  "INTERNSHIP", "FULL_TIME", "PART_TIME", "CONTRACT", "FREELANCE", "RESEARCH", "APPRENTICESHIP",
  "TEMPORARY", "OTHER",
] as const;

export const SECTIONS: SectionDef[] = [
  {
    key: "experience",
    label: "Experience",
    singular: "experience",
    icon: Briefcase,
    description: "Jobs and internships. Each achievement becomes a citable fact.",
    fields: [
      { name: "role", label: "Role", type: "text", required: true },
      { name: "organization", label: "Organization", type: "text", required: true },
      { name: "employment_type", label: "Type", type: "select", options: options(EMPLOYMENT_TYPES) },
      { name: "location", label: "Location", type: "text" },
      { name: "start_date", label: "Start", type: "month" },
      { name: "end_date", label: "End", type: "month" },
      { name: "is_current", label: "I currently work here", type: "checkbox" },
      { name: "description", label: "Description", type: "textarea", wide: true },
      {
        name: "achievements",
        label: "Achievements",
        type: "lines",
        wide: true,
        description: "One per line. Be specific and only include what you can back up.",
      },
      { name: "technologies", label: "Technologies", type: "tags", wide: true },
      { name: "url", label: "Link", type: "url", wide: true },
    ],
    title: (i) => `${str(i.role)} · ${str(i.organization)}`,
    subtitle: (i) =>
      join(formatPeriod(str(i.start_date), str(i.end_date), Boolean(i.is_current)), str(i.location)),
    bullets: (i) => list(i.achievements),
    tags: (i) => list(i.technologies),
  },
  {
    key: "projects",
    label: "Projects",
    singular: "project",
    icon: FolderGit2,
    description: "Things you built. Highlights and metrics become citable facts.",
    fields: [
      { name: "name", label: "Name", type: "text", required: true },
      { name: "role", label: "Your role", type: "text" },
      { name: "description", label: "Description", type: "textarea", wide: true },
      { name: "highlights", label: "Highlights", type: "lines", wide: true, description: "One per line." },
      { name: "metrics", label: "Metrics", type: "lines", wide: true, description: "Measured results only." },
      { name: "impact", label: "Impact", type: "textarea", wide: true },
      { name: "technologies", label: "Technologies", type: "tags", wide: true },
      { name: "url", label: "Live link", type: "url" },
      { name: "repository_url", label: "Repository", type: "url" },
      { name: "start_date", label: "Start", type: "month" },
      { name: "end_date", label: "End", type: "month" },
    ],
    title: (i) => str(i.name),
    subtitle: (i) => join(str(i.role), formatPeriod(str(i.start_date), str(i.end_date))),
    bullets: (i) => [...list(i.highlights), ...list(i.metrics)],
    tags: (i) => list(i.technologies),
  },
  {
    key: "research",
    label: "Research",
    singular: "research experience",
    icon: FlaskConical,
    description: "Lab work, theses and research projects.",
    fields: [
      { name: "title", label: "Title", type: "text", required: true, wide: true },
      { name: "organization", label: "Lab / organization", type: "text", required: true },
      { name: "supervisor", label: "Supervisor", type: "text" },
      { name: "description", label: "Description", type: "textarea", wide: true },
      { name: "methods", label: "Methods", type: "lines", wide: true },
      { name: "outcomes", label: "Outcomes", type: "lines", wide: true },
      { name: "technologies", label: "Technologies", type: "tags", wide: true },
      { name: "start_date", label: "Start", type: "month" },
      { name: "end_date", label: "End", type: "month" },
      { name: "is_current", label: "Ongoing", type: "checkbox" },
      { name: "url", label: "Link", type: "url", wide: true },
    ],
    title: (i) => str(i.title),
    subtitle: (i) =>
      join(str(i.organization), str(i.supervisor) && `with ${str(i.supervisor)}`,
        formatPeriod(str(i.start_date), str(i.end_date), Boolean(i.is_current))),
    bullets: (i) => list(i.outcomes),
    tags: (i) => [...list(i.methods), ...list(i.technologies)],
  },
  {
    key: "education",
    label: "Education",
    singular: "education entry",
    icon: GraduationCap,
    description: "Degrees and programmes.",
    fields: [
      { name: "institution", label: "Institution", type: "text", required: true },
      { name: "degree", label: "Degree", type: "text", required: true },
      { name: "field", label: "Field of study", type: "text" },
      { name: "gpa", label: "GPA", type: "text", placeholder: "e.g. 8.7/10" },
      { name: "start_date", label: "Start", type: "month" },
      { name: "end_date", label: "End (or expected)", type: "month" },
      { name: "is_current", label: "Currently enrolled", type: "checkbox" },
      { name: "location", label: "Location", type: "text" },
      { name: "coursework", label: "Relevant coursework", type: "tags", wide: true },
      { name: "honors", label: "Honors", type: "lines", wide: true },
      { name: "description", label: "Notes", type: "textarea", wide: true },
    ],
    title: (i) => `${str(i.degree)}${str(i.field) ? ` in ${str(i.field)}` : ""}`,
    subtitle: (i) =>
      join(str(i.institution), formatPeriod(str(i.start_date), str(i.end_date), Boolean(i.is_current)),
        str(i.gpa) && `GPA ${str(i.gpa)}`),
    bullets: (i) => list(i.honors),
    tags: (i) => list(i.coursework),
  },
  {
    key: "publications",
    label: "Publications",
    singular: "publication",
    icon: BookOpen,
    description: "Papers, preprints and articles.",
    fields: [
      { name: "title", label: "Title", type: "text", required: true, wide: true },
      { name: "venue", label: "Venue", type: "text" },
      {
        name: "status",
        label: "Status",
        type: "select",
        options: options(["PUBLISHED", "ACCEPTED", "UNDER_REVIEW", "PREPRINT", "IN_PREPARATION"]),
      },
      { name: "year", label: "Year", type: "number" },
      { name: "authors", label: "Authors", type: "tags", wide: true },
      { name: "url", label: "Link", type: "url", wide: true },
      { name: "summary", label: "Summary", type: "textarea", wide: true },
    ],
    title: (i) => str(i.title),
    subtitle: (i) => join(str(i.venue), i.year ? String(i.year) : null, titleCase(str(i.status))),
    tags: (i) => list(i.authors),
  },
  {
    key: "skills",
    label: "Skills",
    singular: "skill",
    icon: Wrench,
    description: "Names are normalised automatically (k8s → Kubernetes).",
    fields: [
      { name: "name", label: "Skill", type: "text", required: true },
      {
        name: "proficiency",
        label: "Proficiency",
        type: "select",
        options: options(["BEGINNER", "INTERMEDIATE", "ADVANCED", "EXPERT"]),
      },
      { name: "years_experience", label: "Years of experience", type: "number" },
    ],
    title: (i) => str(i.name),
    subtitle: (i) =>
      join(titleCase(str(i.category)), i.proficiency ? titleCase(str(i.proficiency)) : null,
        i.years_experience ? `${String(i.years_experience)} yrs` : null),
  },
  {
    key: "achievements",
    label: "Achievements",
    singular: "achievement",
    icon: Award,
    description: "Awards, competitions, leadership, teaching and certifications.",
    fields: [
      { name: "title", label: "Title", type: "text", required: true, wide: true },
      {
        name: "kind",
        label: "Kind",
        type: "select",
        options: options(["AWARD", "COMPETITION", "LEADERSHIP", "TEACHING", "CERTIFICATION", "VOLUNTEERING", "OTHER"]),
      },
      { name: "organization", label: "Organization", type: "text" },
      { name: "achieved_on", label: "Date", type: "date" },
      { name: "url", label: "Link", type: "url" },
      { name: "description", label: "Description", type: "textarea", wide: true },
    ],
    title: (i) => str(i.title),
    subtitle: (i) => join(titleCase(str(i.kind)), str(i.organization), formatMonth(str(i.achieved_on))),
    bullets: (i) => (str(i.description) ? [str(i.description)] : []),
  },
  {
    key: "facts",
    label: "Career facts",
    singular: "fact",
    icon: Quote,
    description:
      "Atomic statements the agent may cite. Facts derived from your items stay in sync automatically.",
    fields: [
      { name: "fact", label: "Fact", type: "textarea", required: true, wide: true },
      {
        name: "category",
        label: "Category",
        type: "select",
        options: options(["GENERAL", "EXPERIENCE", "PROJECT", "RESEARCH", "EDUCATION", "ACHIEVEMENT", "METRIC", "SKILL"]),
      },
      { name: "context", label: "Context", type: "text", wide: true },
    ],
    title: (i) => str(i.fact),
    subtitle: (i) => join(titleCase(str(i.category)), str(i.context)),
    readOnly: (i) =>
      i.origin === "DERIVED" ? "Derived from your profile — edit the source item instead." : null,
  },
  {
    key: "answers",
    label: "Reusable answers",
    singular: "answer",
    icon: MessageSquareQuote,
    description: "Verified answers to questions that application forms ask again and again.",
    fields: [
      { name: "question", label: "Question", type: "textarea", required: true, wide: true },
      { name: "answer", label: "Answer", type: "textarea", required: true, wide: true },
      {
        name: "category",
        label: "Category",
        type: "select",
        options: options(["WORK_AUTHORIZATION", "SPONSORSHIP", "RELOCATION", "SALARY", "AVAILABILITY", "MOTIVATION", "EXPERIENCE", "DEMOGRAPHIC", "OTHER"]),
      },
      { name: "tags", label: "Tags", type: "tags" },
    ],
    title: (i) => str(i.question),
    bullets: (i) => [str(i.answer)],
    subtitle: (i) => titleCase(str(i.category)),
  },
];

export const SECTION_BY_KEY = Object.fromEntries(SECTIONS.map((s) => [s.key, s])) as Record<
  SectionKey,
  SectionDef
>;

export type ProfileData = Schema<"ProfileOut">;
