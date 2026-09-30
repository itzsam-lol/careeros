"""Tailor a LaTeX resume to one job without inventing anything.

Everything the tailor does is one of:

* **reorder** bullets, entries and skills so the most relevant come first;
* **select** which projects to show from the user's verified project library;
* **add** a skill to an existing skills line only when it is a verified profile skill the job asks for;
* **trim** the least relevant bullets until the resume fits its page budget;
* optionally **rephrase** bullets/summary with an LLM, accepted only if a validator proves the
  rewrite adds no new numbers, skills or claims (otherwise the original text is kept).

Every change is recorded so the user can see exactly what was done and why.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable, Iterable
from dataclasses import dataclass, field
from typing import Any

from careeros.intelligence.skills import canonical_key, extract_skill_names, lookup
from careeros.resumes.document import (
    Bullet,
    Entry,
    ListBlock,
    ResumeDoc,
    Section,
    SkillLine,
    normalize_key,
    parse,
    plain_text,
)
from careeros.resumes.latex import escape

__all__ = ["canonical_key"]  # re-exported for callers building allow-lists

_STOP = set(
    """a an and are as at be by for from has have in into is it its of on or our that the their this to we
    will with you your they them who what when where which while about across over under more most
    team teams work working role roles experience years year strong ability skills using use used able
    etc including include includes like new also well within per via based good great plus""".split()
)
_WORD = re.compile(r"[a-z][a-z0-9+#.-]{2,}")
_NUMBER = re.compile(r"\d[\d,.]*\s*%?\+?")
MASTER_BONUS = 1.5
EXPERIENCE_PROTECTION = 2.0


@dataclass
class JobTarget:
    """What the resume is being tailored for (all derived from the job analysis)."""

    title: str
    company: str
    required_skills: list[str] = field(default_factory=list)
    preferred_skills: list[str] = field(default_factory=list)
    keywords: list[str] = field(default_factory=list)
    responsibilities: list[str] = field(default_factory=list)
    description: str = ""

    @classmethod
    def from_extraction(
        cls, title: str, company: str, extraction: dict[str, Any], description: str = ""
    ) -> JobTarget:
        return cls(
            title=title,
            company=company,
            required_skills=list(extraction.get("required_skills") or []),
            preferred_skills=list(extraction.get("preferred_skills") or []),
            keywords=list(extraction.get("keywords") or []),
            responsibilities=list(extraction.get("responsibilities") or []),
            description=description,
        )


@dataclass
class LibraryProject:
    """A verified profile project that can be shown on the resume."""

    name: str
    technologies: list[str]
    highlights: list[str]
    url: str | None = None


@dataclass
class TailorOptions:
    max_projects: int | None = None  # default: as many as the master resume shows
    max_pages: int = 1
    add_skills: bool = True
    swap_projects: bool = True
    rephrase: bool = False
    max_added_skills: int = 5


@dataclass
class Change:
    kind: str  # reorder | swap_in | swap_out | add_skill | trim | rephrase
    detail: str


@dataclass
class TailorResult:
    tex: str
    changes: list[Change]
    keywords_before: dict[str, bool]
    keywords_after: dict[str, bool]
    relevance: float

    @property
    def coverage_before(self) -> float:
        return _ratio(self.keywords_before)

    @property
    def coverage_after(self) -> float:
        return _ratio(self.keywords_after)


def _trailing(text: str) -> str:
    """The whitespace at the end of `text`."""
    return text[len(text.rstrip()) :]


def _ratio(hits: dict[str, bool]) -> float:
    return round(sum(hits.values()) / len(hits), 3) if hits else 1.0


class Scorer:
    """Relevance of a piece of resume text to the job (skills first, then vocabulary)."""

    def __init__(self, target: JobTarget) -> None:
        self.skills: dict[str, float] = {}
        for weight, names in (
            (3.0, target.required_skills),
            (2.0, target.preferred_skills),
            (1.0, target.keywords),
        ):
            for name in names:
                known = lookup(name)
                key = canonical_key(known.name if known else name)
                if key:
                    self.skills[key] = max(self.skills.get(key, 0.0), weight)
        self.words: dict[str, float] = {}
        vocab_sources = [
            (1.5, target.title),
            (0.6, " ".join(target.responsibilities)),
            (0.25, target.description[:6000]),
        ]
        for weight, text in vocab_sources:
            for word in _WORD.findall(text.lower()):
                if word not in _STOP:
                    self.words[word] = max(self.words.get(word, 0.0), weight)

    def skills_in(self, text: str) -> set[str]:
        found = {canonical_key(name) for name in extract_skill_names(text)}
        lowered = text.lower()
        # Job keywords that are not in the taxonomy still count when they appear verbatim.
        found |= {key for key in self.skills if len(key) > 3 and key in canonical_key(lowered)}
        return found

    def score(self, text: str) -> float:
        skills = self.skills_in(text)
        skill_score = sum(self.skills.get(key, 0.0) for key in skills)
        words = set(_WORD.findall(text.lower()))
        vocab_score = sum(self.words.get(word, 0.0) for word in words)
        return skill_score + 0.35 * vocab_score


# --- rendering library projects in the master's style ---------------------------------------


_HEADER_STYLE = re.compile(
    r"^(?P<indent>[ \t]*)\\noindent\\textbf\{(?P<name>.*?)\}(?P<mid>.*?)\\textit\{(?P<sub>.*?)\}(?P<after>.*)$",
    re.S,
)


def _render_library_entry(
    project: LibraryProject, style_source: Entry | None, scorer: Scorer, template: ListBlock | None
) -> Entry:
    ranked_tech = sorted(project.technologies, key=lambda t: -scorer.score(t))[:3]
    tech = escape(", ".join(ranked_tech))
    name = escape(project.name)
    link = ""
    if project.url:
        display = re.sub(r"^https?://(www\.)?", "", project.url).rstrip("/")
        link = f"\\href{{{project.url}}}{{{escape(display)}}}"
    header = f"\\noindent\\textbf{{{name}}}"
    if style_source is not None and (m := _HEADER_STYLE.match(style_source.header)):
        mid = m.group("mid")
        header = f"{m.group('indent')}\\noindent\\textbf{{{name}}}{mid}\\textit{{{tech}}}"
        header += f"\\hfill {link}\n" if link else "\n"
    else:
        header += f" \\enspace|\\enspace \\textit{{{tech}}}" + (
            f"\\hfill {link}\n" if link else "\n"
        )
    lead = template.bullets[0].lead if template and template.bullets else "  \\item "
    bullets = [Bullet(tex=escape(text) + "\n", lead=lead) for text in project.highlights]
    items = ListBlock(
        env=template.env if template else "itemize",
        begin=template.begin if template else "\\begin{itemize}",
        before_first=template.before_first if template else "\n",
        bullets=bullets,
        end=template.end if template else "\\end{itemize}",
    )
    return Entry(
        header=header, items=items, trailer="\n", source="library", key=normalize_key(project.name)
    )


# --- the tailoring pipeline ----------------------------------------------------------------


def _reorder_bullets(bullets: list[Bullet], scorer: Scorer) -> tuple[list[Bullet], bool]:
    scored = sorted(enumerate(bullets), key=lambda pair: (-scorer.score(pair[1].text), pair[0]))
    ordered = [bullet for _, bullet in scored]
    return _fix_trailing(ordered, bullets), ordered != bullets


def _fix_trailing(ordered: list[Bullet], original: list[Bullet]) -> list[Bullet]:
    """Keep the exact whitespace layout: every bullet ends like the original ones did."""
    if not original:
        return ordered
    last_tail = _trailing(original[-1].tex)
    inner_tail = _trailing(original[0].tex) if len(original) > 1 else last_tail
    fixed = []
    for index, bullet in enumerate(ordered):
        body = bullet.tex.rstrip()
        tail = last_tail if index == len(ordered) - 1 else inner_tail
        fixed.append(Bullet(tex=body + tail, lead=bullet.lead))
    return fixed


def keyword_hits(doc_text: str, target: JobTarget) -> dict[str, bool]:
    wanted: dict[str, str] = {}
    for name in [*target.required_skills, *target.preferred_skills]:
        skill = lookup(name)
        display = skill.name if skill else name
        wanted.setdefault(canonical_key(display), display)
    present = {canonical_key(n) for n in extract_skill_names(doc_text)}
    squashed = canonical_key(doc_text)
    return {
        display: (key in present or (len(key) > 3 and key in squashed))
        for key, display in wanted.items()
    }


def tailor(
    master_tex: str,
    target: JobTarget,
    *,
    library: Iterable[LibraryProject] = (),
    verified_skills: Iterable[str] = (),
    options: TailorOptions | None = None,
) -> tuple[ResumeDoc, TailorResult]:
    """Deterministic tailoring (no LLM). Page fitting happens later, in `fit_to_pages`."""
    options = options or TailorOptions()
    scorer = Scorer(target)
    doc = parse(master_tex)
    changes: list[Change] = []
    before = keyword_hits(doc.text, target)

    for section in doc.sections:
        role = section.role
        if section.kind == "entries" and role in ("experience", "research", "leadership"):
            for entry in section.entries:
                if entry.items and len(entry.items.bullets) > 1:
                    entry.items.bullets, moved = _reorder_bullets(entry.items.bullets, scorer)
                    if moved:
                        section.changed = True
                        changes.append(
                            Change("reorder", f"Put the most relevant {entry.title} bullets first")
                        )
        elif section.kind == "entries" and role == "projects":
            _tailor_projects(section, list(library), scorer, options, changes)
        elif (
            section.kind == "list"
            and section.listing is not None
            and len(section.listing.bullets) > 1
        ):
            section.listing.bullets, moved = _reorder_bullets(section.listing.bullets, scorer)
            if moved:
                section.changed = True
                changes.append(Change("reorder", f"Reordered {section.title} by relevance"))
        elif section.kind == "skills":
            _tailor_skills(section, scorer, list(verified_skills), options, changes, doc)

    after = keyword_hits(doc.text, target)
    relevance = scorer.score(doc.text)
    result = TailorResult(
        tex=doc.render(),
        changes=changes,
        keywords_before=before,
        keywords_after=after,
        relevance=relevance,
    )
    return doc, result


def _tailor_projects(
    section: Section,
    library: list[LibraryProject],
    scorer: Scorer,
    options: TailorOptions,
    changes: list[Change],
) -> None:
    master = section.entries
    if not master:
        return
    style = master[0]
    template = next((e.items for e in master if e.items), None)
    candidates = list(master)
    shown = {entry.key for entry in master}
    if options.swap_projects:
        for project in library:
            key = normalize_key(project.name)
            if key and key not in shown and project.highlights:
                candidates.append(_render_library_entry(project, style, scorer, template))
                shown.add(key)

    known = {normalize_key(project.name): project for project in library}

    def entry_score(entry: Entry) -> float:
        text = entry.text
        # The resume may not print a project's tech stack; the verified profile knows it.
        if entry.source == "master" and (project := known.get(entry.key)):
            text += " " + " ".join(project.technologies)
        # Each skill counts once per project; projects the user chose for the master get a nudge.
        return scorer.score(text) + (MASTER_BONUS if entry.source == "master" else 0.0)

    limit = options.max_projects or len(master)
    ranked = sorted(candidates, key=lambda e: (-entry_score(e), candidates.index(e)))
    chosen = ranked[:limit]
    for entry in chosen:
        if entry.items and len(entry.items.bullets) > 1:
            entry.items.bullets, _ = _reorder_bullets(entry.items.bullets, scorer)
    dropped = [e.title for e in master if e not in chosen]
    added = [e.title for e in chosen if e.source == "library"]
    if chosen != master or dropped or added:
        section.entries = chosen
        section.changed = True
    for title in added:
        matched = sorted(
            scorer.skills_in(next(e for e in chosen if e.title == title).text)
            & scorer.skills.keys()
        )
        note = f" (matches {', '.join(_display(k) for k in matched[:4])})" if matched else ""
        changes.append(Change("swap_in", f"Added project {title}{note}"))
    for title in dropped:
        changes.append(Change("swap_out", f"Left out {title} to make room for more relevant work"))
    if not added and not dropped and chosen != master:
        changes.append(Change("reorder", "Ordered projects by relevance to this role"))


def _display(key: str) -> str:
    skill = lookup(key)
    return skill.name if skill else key


def _tailor_skills(
    section: Section,
    scorer: Scorer,
    verified: list[str],
    options: TailorOptions,
    changes: list[Change],
    doc: ResumeDoc,
) -> None:
    moved_any = False
    for line in section.skills:
        ranked = sorted(
            enumerate(line.items), key=lambda pair: (-scorer.score(plain_text(pair[1])), pair[0])
        )
        new_items = [item for _, item in ranked]
        if new_items != line.items:
            line.items = new_items
            moved_any = True
    if moved_any:
        section.changed = True
        changes.append(Change("reorder", "Listed the skills this role asks for first"))
    if not options.add_skills:
        return
    present = {canonical_key(n) for n in extract_skill_names(doc.text)} | {
        canonical_key(plain_text(item)) for line in section.skills for item in line.items
    }
    candidates = [
        name
        for name in verified
        if canonical_key(name) in scorer.skills and canonical_key(name) not in present
    ]
    candidates.sort(key=lambda name: -scorer.skills.get(canonical_key(name), 0))
    added = 0
    for name in candidates:
        if added >= options.max_added_skills:
            break
        target_line = _best_line(section, name)
        if target_line is None:
            continue
        target_line.items.insert(_insert_position(target_line, scorer), escape(name))
        section.changed = True
        added += 1
        changes.append(
            Change(
                "add_skill",
                f"Added {name} to {target_line.label} (a verified skill the role asks for)",
            )
        )


def _best_line(section: Section, skill_name: str) -> SkillLine | None:
    """The skills line whose existing items share the new skill's category (never spoken languages)."""
    from careeros.intelligence.skills import skill_category

    category = skill_category(skill_name).value
    data_like = category in ("DATA", "ML_AI")
    label_words = (
        ("data", "analytic", "machine", "ml", " ai", "statistic")
        if data_like
        else (
            "technolog",
            "tools",
            "technical",
            "engineering",
            "programming",
            "software",
            "development",
            "frameworks",
        )
    )
    lines = [
        line
        for line in section.skills
        if not ("language" in line.label.lower() and "programming" not in line.label.lower())
    ]
    for line in lines:
        if any(word in f" {line.label.lower()}" for word in label_words):
            return line
    best, best_count = None, 0
    for line in lines:
        count = sum(1 for item in line.items if skill_category(plain_text(item)).value == category)
        if count > best_count:
            best, best_count = line, count
    return best or (lines[-1] if lines else None)


def _insert_position(line: SkillLine, scorer: Scorer) -> int:
    """After the items that already match the job, so matched skills stay grouped at the front."""
    position = 0
    for index, item in enumerate(line.items):
        if scorer.score(plain_text(item)) > 0:
            position = index + 1
    return position


# --- page fitting ---------------------------------------------------------------------------


def trim_one(doc: ResumeDoc, scorer: Scorer) -> Change | None:
    """Remove the least relevant removable bullet (or, as a last resort, the weakest project)."""
    best: tuple[float, list[Bullet], int, str] | None = None
    for section in doc.sections:
        if section.role in ("education", "summary", "skills"):
            continue
        lists: list[tuple[list[Bullet], str, int]] = []
        if section.kind == "entries":
            for entry in section.entries:
                if entry.items:
                    lists.append(
                        (entry.items.bullets, entry.title, 1 if section.role != "experience" else 2)
                    )
        elif section.kind == "list" and section.listing is not None:
            lists.append((section.listing.bullets, section.title, 2))
        # Work experience is the most valuable content: trim projects and activities first.
        protect = EXPERIENCE_PROTECTION if section.role == "experience" else 0.0
        for bullets, owner, minimum in lists:
            if len(bullets) <= minimum:
                continue
            for index, bullet in enumerate(bullets):
                # On ties, trim the later bullet: earlier ones were placed first for a reason.
                score = scorer.score(bullet.text) + protect - 0.001 * index
                if best is None or score < best[0]:
                    best = (score, bullets, index, owner)
    if best is not None:
        _, bullets, index, owner = best
        removed = bullets.pop(index)
        if index == len(bullets) and bullets:
            # Removed the last bullet: keep the list's closing whitespace on the new last one.
            bullets[-1] = Bullet(
                tex=bullets[-1].tex.rstrip() + _trailing(removed.tex), lead=bullets[-1].lead
            )
        for section in doc.sections:
            section.changed = True if section.kind in ("entries", "list") else section.changed
        return Change("trim", f"Shortened {owner} to fit the page")
    projects = doc.section("projects")
    if projects and projects.kind == "entries" and len(projects.entries) > 1:
        weakest = min(projects.entries, key=lambda e: scorer.score(e.text))
        projects.entries.remove(weakest)
        projects.changed = True
        return Change("trim", f"Left out {weakest.title} to fit the page")
    return None


# --- grounded rephrasing ----------------------------------------------------------------------


def validate_rewrite(original: str, rewrite: str, allowed_skills: set[str]) -> str | None:
    """Why a rewrite is unacceptable, or None when it only rephrases facts already present."""
    rewrite = rewrite.strip()
    if not rewrite:
        return "empty"
    if not 0.6 <= len(rewrite) / max(len(original), 1) <= 1.35:
        return "length changed too much"
    numbers_before = {n.strip().rstrip("+%.,") for n in _NUMBER.findall(original)}
    numbers_after = {n.strip().rstrip("+%.,") for n in _NUMBER.findall(rewrite)}
    if not numbers_after <= numbers_before:
        return f"introduced numbers {sorted(numbers_after - numbers_before)}"
    if numbers_before - numbers_after:
        return f"dropped numbers {sorted(numbers_before - numbers_after)}"
    skills_before = {canonical_key(s) for s in extract_skill_names(original)}
    skills_after = {canonical_key(s) for s in extract_skill_names(rewrite)}
    new_skills = skills_after - skills_before - allowed_skills
    if new_skills:
        return f"introduced skills {sorted(new_skills)}"
    proper_before = set(re.findall(r"\b[A-Z][A-Za-z0-9]+\b", original))
    proper_after = set(re.findall(r"\b[A-Z][A-Za-z0-9]+\b", rewrite))
    sentence_starts = set(re.findall(r"(?:^|[.;:]\s+)([A-Z][a-z]+)", rewrite))
    invented = (
        proper_after - proper_before - sentence_starts - {_display(k) for k in allowed_skills}
    )
    if invented:
        return f"introduced names {sorted(invented)[:5]}"
    return None


Rewriter = Callable[[list[dict[str, str]], JobTarget], Awaitable[dict[str, str]]]


async def rephrase(
    doc: ResumeDoc,
    target: JobTarget,
    rewriter: Rewriter,
    allowed_skills: set[str],
    changes: list[Change],
    limit: int = 8,
) -> None:
    """Ask `rewriter` to align wording with the job; keep only rewrites that pass validation."""
    scorer = Scorer(target)
    candidates: list[tuple[str, Bullet]] = []
    for section in doc.sections:
        bullet_lists: list[list[Bullet]] = []
        if section.kind == "entries" and section.role in ("experience", "projects", "research"):
            bullet_lists = [e.items.bullets for e in section.entries if e.items]
        for bullets in bullet_lists:
            for bullet in bullets:
                if re.search(r"\\(?!&|%|\$|#|_)[A-Za-z]", bullet.tex):
                    continue  # contains formatting commands; leave it alone
                candidates.append((f"b{len(candidates)}", bullet))
    candidates.sort(key=lambda pair: -scorer.score(pair[1].text))
    chosen = candidates[:limit]
    if not chosen:
        return
    payload = [{"id": key, "text": bullet.text} for key, bullet in chosen]
    rewrites = await rewriter(payload, target)
    for key, bullet in chosen:
        new_text = rewrites.get(key)
        if not new_text or new_text.strip() == bullet.text:
            continue
        problem = validate_rewrite(bullet.text, new_text, allowed_skills)
        if problem:
            changes.append(Change("rephrase_rejected", f"Kept original wording ({problem})"))
            continue
        trailing = _trailing(bullet.tex)
        bullet.tex = escape(new_text.strip()) + trailing
        changes.append(
            Change("rephrase", f"Reworded to match the role: \u201c{new_text.strip()[:90]}\u201d")
        )
    for section in doc.sections:
        if section.kind == "entries":
            section.changed = True
