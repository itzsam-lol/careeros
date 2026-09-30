r"""A structural view of a one-column LaTeX resume that renders back to identical source.

The parser understands the common "section / entry / bullet list / skills line" layout:

    \section{Experience}
    \noindent\textbf{Company}\hfill City\\ ...      <- entry header
    \begin{itemize-like}  \item ...  \end{...}       <- bullets
    \vspace{3pt}                                     <- separator between entries

Anything it does not recognise is kept verbatim, so tailoring only ever touches sections it
fully understands. `render(parse(tex)) == tex` holds for every input.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

SECTION_RE = re.compile(r"\\section\*?\{")
ENTRY_START_RE = re.compile(r"^[ \t]*\\noindent\\textbf\{", re.M)
LIST_BEGIN_RE = re.compile(r"\\begin\{(?P<env>[A-Za-z*]+)\}")
ITEM_RE = re.compile(r"^[ \t]*\\item\b[ \t]*", re.M)
LIST_ENVS = {"itemize", "enumerate", "bl", "bullets", "compactitem", "itemize*"}


def _matching_brace(text: str, open_index: int) -> int:
    """Index of the brace closing the one at `open_index` (which must be '{')."""
    depth = 0
    i = open_index
    while i < len(text):
        char = text[i]
        if char == "\\":
            i += 2
            continue
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise ValueError("Unbalanced braces in LaTeX source")


def plain_text(tex: str) -> str:
    """Rough LaTeX -> text for scoring and keyword checks (not for display)."""
    text = re.sub(r"\\href\{[^}]*\}\{([^}]*)\}", r"\1", tex)
    text = re.sub(r"\\(?:textbf|textit|emph|underline|texttt|textsc|mbox)\{([^}]*)\}", r"\1", text)
    text = text.replace("\\&", "&").replace("\\%", "%").replace("\\$", "$").replace("\\#", "#")
    text = text.replace("\\_", "_").replace("--", "-").replace("``", '"').replace("''", '"')
    text = re.sub(r"\\[A-Za-z]+\*?(\[[^\]]*\])?", " ", text)
    text = text.replace("{", " ").replace("}", " ").replace("~", " ")
    return re.sub(r"\s+", " ", text).strip()


@dataclass
class Bullet:
    tex: str  # the item body, without the leading "\item "
    lead: str = "  \\item "  # exact text that preceded it (indentation + \item)

    @property
    def text(self) -> str:
        return plain_text(self.tex)


@dataclass
class ListBlock:
    env: str
    begin: str  # e.g. "\begin{bl}" (+ options) as written
    before_first: str  # whitespace between \begin and the first \item
    bullets: list[Bullet]
    end: str  # "\end{bl}" as written, including whitespace before it

    def render(self) -> str:
        return (
            self.begin
            + self.before_first
            + "".join(b.lead + b.tex for b in self.bullets)
            + self.end
        )


@dataclass
class Entry:
    header: str
    items: ListBlock | None
    trailer: str  # text after the list (usually a newline)
    source: str = "master"  # "master" or "library" (added from the profile)
    key: str = ""

    def render(self) -> str:
        return self.header + (self.items.render() if self.items else "") + self.trailer

    @property
    def title(self) -> str:
        match = re.search(r"\\textbf\{", self.header)
        if not match:
            return plain_text(self.header)[:80]
        end = _matching_brace(self.header, match.end() - 1)
        return plain_text(self.header[match.end() : end])

    @property
    def text(self) -> str:
        bullets = " ".join(b.text for b in self.items.bullets) if self.items else ""
        return f"{plain_text(self.header)} {bullets}"


@dataclass
class SkillLine:
    lead: str  # e.g. "\textbf{Data \& Analytics:} "
    items: list[str]
    sep: str  # line terminator as written, e.g. "\\[2pt]\n" or "\n"

    @property
    def label(self) -> str:
        return plain_text(self.lead).rstrip(":").strip()

    def render(self) -> str:
        return self.lead + ", ".join(self.items) + self.sep


@dataclass
class Section:
    head: str  # "\section{Title}" as written
    title: str  # plain title text
    body: str  # original body (always kept for verbatim rendering)
    kind: str = "raw"  # raw | summary | entries | list | skills
    intro: str = ""  # entries/list: text before the first entry or list
    entries: list[Entry] = field(default_factory=list)
    separator: str = "\\vspace{3pt}\n"
    listing: ListBlock | None = None
    outro: str = ""
    summary_lead: str = ""
    summary: str = ""
    summary_tail: str = ""
    skills: list[SkillLine] = field(default_factory=list)
    changed: bool = False

    @property
    def role(self) -> str:
        """What the section is for, from its title."""
        title = self.title.lower()
        for role, words in (
            ("summary", ("summary", "profile", "objective", "about")),
            ("education", ("education", "academic")),
            ("experience", ("experience", "employment", "work history", "internship")),
            ("projects", ("project",)),
            ("skills", ("skill", "technical", "technolog")),
            ("research", ("research", "publication")),
            (
                "leadership",
                (
                    "leadership",
                    "volunteer",
                    "activities",
                    "extracurricular",
                    "achievement",
                    "award",
                ),
            ),
        ):
            if any(word in title for word in words):
                return role
        return "other"

    def render(self) -> str:
        if not self.changed:
            return self.head + self.body
        if self.kind == "summary":
            return self.head + self.summary_lead + self.summary + self.summary_tail
        if self.kind == "entries":
            parts = [entry.render() for entry in self.entries]
            joined = ""
            for index, part in enumerate(parts):
                if index > 0 and not joined.endswith("\n"):
                    joined += "\n"
                joined += (self.separator if index > 0 else "") + part
            return self.head + self.intro + joined + self.outro
        if self.kind == "list" and self.listing is not None:
            return self.head + self.intro + self.listing.render() + self.outro
        if self.kind == "skills":
            return (
                self.head + self.intro + "".join(line.render() for line in self.skills) + self.outro
            )
        return self.head + self.body


@dataclass
class ResumeDoc:
    preamble: str
    sections: list[Section]
    tail: str

    def render(self) -> str:
        return self.preamble + "".join(section.render() for section in self.sections) + self.tail

    def section(self, role: str) -> Section | None:
        return next((s for s in self.sections if s.role == role), None)

    @property
    def text(self) -> str:
        return plain_text(self.render().split("\\begin{document}", 1)[-1])


# --- parsing ------------------------------------------------------------------------------


def _parse_list(text: str) -> tuple[ListBlock, int, int] | None:
    """Find the first bullet list in `text`: (block, start, end) or None."""
    begin = LIST_BEGIN_RE.search(text)
    if not begin or begin.group("env") not in LIST_ENVS:
        return None
    env = begin.group("env")
    begin_end = begin.end()
    if begin_end < len(text) and text[begin_end] == "[":  # \begin{itemize}[options]
        close = text.index("]", begin_end)
        begin_end = close + 1
    end_tag = f"\\end{{{env}}}"
    end_index = text.find(end_tag, begin_end)
    if end_index == -1:
        return None
    inner = text[begin_end:end_index]
    starts = list(ITEM_RE.finditer(inner))
    if not starts:
        return None
    before_first = inner[: starts[0].start()]
    bullets: list[Bullet] = []
    for index, match in enumerate(starts):
        stop = starts[index + 1].start() if index + 1 < len(starts) else len(inner)
        body = inner[match.end() : stop]
        # Keep trailing whitespace/newline with the bullet so re-rendering is exact.
        bullets.append(Bullet(tex=body, lead=match.group(0)))
    # Whitespace before \end{...} belongs to the last bullet; move nothing (exact render).
    block = ListBlock(
        env=env,
        begin=text[begin.start() : begin_end],
        before_first=before_first,
        bullets=bullets,
        end=end_tag,
    )
    return block, begin.start(), end_index + len(end_tag)


def _parse_entries(section: Section) -> None:
    body = section.body
    starts = [m.start() for m in ENTRY_START_RE.finditer(body)]
    if not starts:
        return
    section.intro = body[: starts[0]]
    chunks = [
        body[start : starts[i + 1] if i + 1 < len(starts) else len(body)]
        for i, start in enumerate(starts)
    ]
    entries: list[Entry] = []
    separator = None
    for index, chunk in enumerate(chunks):
        parsed = _parse_list(chunk)
        if parsed is None:
            header, items, rest = chunk, None, ""
        else:
            block, start, end = parsed
            header, items, rest = chunk[:start], block, chunk[end:]
        if index < len(chunks) - 1:
            # Text between this entry's list and the next entry: the separator (e.g. \vspace{3pt}).
            stripped = rest.lstrip("\n")
            newline = rest[: len(rest) - len(stripped)]
            if stripped.strip():
                separator = separator or stripped
                rest = newline
        entries.append(Entry(header=header, items=items, trailer=rest))
    section.entries = entries
    if separator:
        section.separator = separator
    # Normalise trailers so entries can be reordered: each ends with one newline and the
    # whitespace that followed the last entry (before the next section) moves to `outro`.
    section.outro = ""
    last = entries[-1].trailer
    if last.startswith("\n"):
        entries[-1].trailer, section.outro = "\n", last[1:]
    elif not last.strip():
        entries[-1].trailer, section.outro = "", last
    for entry in entries:
        entry.key = normalize_key(entry.title)
    section.kind = "entries"


def _split_items(line: str) -> list[str]:
    """Split a comma list, keeping commas inside parentheses/braces together."""
    items, depth, current = [], 0, ""
    for char in line:
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
        if char == "," and depth == 0:
            items.append(current.strip())
            current = ""
        else:
            current += char
    if current.strip():
        items.append(current.strip())
    return items


def _parse_skills(section: Section) -> None:
    body = section.body
    first = body.find("\\textbf{")
    if first == -1:
        return
    section.intro = body[:first]
    rest = body[first:]
    lines: list[SkillLine] = []
    pattern = re.compile(
        r"(\\textbf\{[^}]*\}\s*)(.*?)(\\\\(?:\[[^\]]*\])?\s*\n|\n\s*\n|\s*$)", re.S
    )
    pos = 0
    while pos < len(rest):
        match = pattern.match(rest, pos)
        if not match or not match.group(0):
            break
        lead, items, sep = match.group(1), match.group(2), match.group(3)
        if "\\\\" in items or "\\begin" in items:
            return  # unexpected structure; keep the section verbatim
        lines.append(SkillLine(lead=lead, items=_split_items(items), sep=sep))
        pos = match.end()
    if not lines:
        return
    section.outro = rest[pos:]
    # The items of the final line may have absorbed trailing whitespace into `sep`.
    section.skills = lines
    section.kind = "skills"


def _parse_summary(section: Section) -> None:
    body = section.body
    text = body.strip()
    if not text or "\\begin" in text or "\\item" in text:
        return
    lead_len = len(body) - len(body.lstrip())
    trail_len = len(body) - len(body.rstrip())
    section.summary_lead = body[:lead_len]
    section.summary = body[lead_len : len(body) - trail_len]
    section.summary_tail = body[len(body) - trail_len :]
    section.kind = "summary"


def normalize_key(title: str) -> str:
    """Identity for matching resume entries to profile items ("LedgerLens: ..." -> "ledgerlens")."""
    head = re.split(r"[:|(\u2013\u2014-]", title, maxsplit=1)[0]
    return re.sub(r"[^a-z0-9]", "", head.lower())


def parse(tex: str) -> ResumeDoc:
    begin = tex.find("\\begin{document}")
    end = tex.rfind("\\end{document}")
    if begin == -1 or end == -1:
        raise ValueError(
            "Not a complete LaTeX document (missing \\begin{document} or \\end{document})"
        )
    matches = list(SECTION_RE.finditer(tex, begin, end))
    if not matches:
        return ResumeDoc(preamble=tex[:end], sections=[], tail=tex[end:])
    preamble = tex[: matches[0].start()]
    sections: list[Section] = []
    for index, match in enumerate(matches):
        close = _matching_brace(tex, match.end() - 1)
        head = tex[match.start() : close + 1]
        stop = matches[index + 1].start() if index + 1 < len(matches) else end
        section = Section(
            head=head, title=plain_text(tex[match.end() : close]), body=tex[close + 1 : stop]
        )
        if section.role == "summary":
            _parse_summary(section)
        elif section.role == "skills":
            _parse_skills(section)
        elif ENTRY_START_RE.search(section.body):
            _parse_entries(section)
        else:
            parsed = _parse_list(section.body)
            if parsed:
                block, start, stop_index = parsed
                section.intro = section.body[:start]
                section.listing = block
                section.outro = section.body[stop_index:]
                section.kind = "list"
        sections.append(section)
    return ResumeDoc(preamble=preamble, sections=sections, tail=tex[end:])
