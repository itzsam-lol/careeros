# Resume engine

CareerOS tailors **your own LaTeX résumé** to each job. It never writes one from scratch and never
states anything that isn't in your verified profile.

## How "trained on your data" works

Nothing is fine-tuned. The agent is grounded instead: every output is assembled from, or checked
against, your verified profile.

- Your profile (experience, projects, research, skills, achievements) is imported and verified by
  you. Only VERIFIED items are used for matching, résumés, cover letters, prep and drafts.
- Job postings are untrusted input. Text addressed to AI tools is detected and ignored.
- When an LLM is configured, it may only **rephrase**, and a validator rejects any rewrite that:
  - adds or drops a number,
  - introduces a skill that isn't verified, or
  - names a new company or product.

## Pipeline

1. **Parse** the master `.tex` into sections, entries, bullets and skills lines
   (`resumes/document.py`). Rendering an unchanged document gives back your exact source, so
   formatting, fonts and macros are preserved.
2. **Score** each bullet and project against the job (`resumes/tailor.py`):
   - required skills weigh 3, preferred skills 2, keywords 1, plus vocabulary from the title and
     responsibilities;
   - skills are matched through the skills taxonomy, so "Postgres" counts as "PostgreSQL".
3. **Tailor**:
   - reorder experience bullets, activities and skills so the most relevant come first;
   - choose the most relevant projects from your verified project library (not only the ones on the
     master), rendered in the same style;
   - add verified skills that the job asks for to the right skills line.
4. **Fit**: compile, count pages, and trim the least relevant bullets until it fits (one page by
   default). Projects and activities are trimmed before work experience.
5. **Record** every change ("Added project X (matches Docker, Redis)", "Shortened Y to fit the page")
   and the skill coverage before and after.

Sections the engine doesn't recognise, plus the summary and education, are kept exactly as written.

## Compilation

Engines are tried in this order: `tectonic`, `xelatex`, `lualatex`, `pdflatex`. Shell escape is
disabled for every engine.

Templates written for pdfLaTeX (`\input{glyphtounicode}`, `\pdfgentounicode`) are guarded
automatically. Curly quotes and dashes are normalised so 8-bit fonts such as Charter render them
under XeTeX too.

## Cover letters, prep and drafts

- **Cover letters** are built from your education, internships and your most relevant verified
  achievements. They claim only that you *have* the skills the role asks for. They compile with your
  résumé's fonts and header as a letterhead.
- **Interview prep** marks each skill the job asks for as *strong* (you have a verified achievement
  using it), *prepare an example* (on your profile but not highlighted) or *gap*. It also suggests
  stories for common behavioural questions and questions to ask.
- **Message drafts** (LinkedIn note, referral request, follow-up, thank-you) are only ever drafts
  for you to edit and send.

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `GET/PUT` | `/api/v1/resumes/master` | Read or upload the master `.tex` (compiled in the background) |
| `POST` | `/api/v1/resumes/master/link` | Signed link to the master PDF |
| `GET/POST` | `/api/v1/resumes` | List documents, or request a résumé or cover letter for a job |
| `GET/PATCH/DELETE` | `/api/v1/resumes/{id}` | Details (changes, coverage, text), star or rename, delete |
| `GET` | `/api/v1/resumes/{id}/pdf` | PDF for the signed-in user |
| `POST` | `/api/v1/resumes/{id}/link` | 15-minute signed link, for phones and browsers |
| `GET` | `/api/v1/jobs/{id}/prep` | Interview prep |
| `GET` | `/api/v1/jobs/{id}/outreach` | Message drafts |
