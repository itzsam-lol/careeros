"""Build tailored resumes and cover letters from the user's master LaTeX and verified profile."""

from __future__ import annotations

import hashlib
import hmac
import re
import time
import uuid
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from careeros.config import LLMTask
from careeros.core.clock import utcnow
from careeros.core.errors import LLMProviderError, NotFoundError, ValidationFailedError
from careeros.core.logging import get_logger
from careeros.intelligence.service import latest_analysis
from careeros.intelligence.skills import extract_skill_names, normalize_skill_name
from careeros.jobs.models import Job
from careeros.llm.prompting import PromptBuilder
from careeros.notifications.models import NotificationPriority, NotificationType
from careeros.notifications.service import notify
from careeros.profile.enums import VerificationStatus
from careeros.profile.service import ProfileSnapshot, get_or_create_profile, load_snapshot
from careeros.resumes import tailor as tailoring
from careeros.resumes.document import parse, plain_text
from careeros.resumes.latex import LatexError, compile_tex, escape
from careeros.resumes.models import DocumentKind, DocumentStatus, ResumeDocument, ResumeMaster
from careeros.tasks.models import TaskType
from careeros.tasks.queue import enqueue
from careeros.users.models import User

if TYPE_CHECKING:
    from careeros.container import Container

log = get_logger(__name__)
_VERIFIED = VerificationStatus.VERIFIED


# --- master template ------------------------------------------------------------------------


async def get_master(session: AsyncSession, user_id: uuid.UUID) -> ResumeMaster | None:
    return (
        await session.execute(select(ResumeMaster).where(ResumeMaster.user_id == user_id))
    ).scalar_one_or_none()


async def set_master(session: AsyncSession, user: User, tex: str, filename: str) -> ResumeMaster:
    try:
        doc = parse(tex)
    except ValueError as exc:
        raise ValidationFailedError(str(exc)) from exc
    if not doc.sections:
        raise ValidationFailedError(
            "No \\section{...} headings found; CareerOS needs them to tailor your resume"
        )
    master = await get_master(session, user.id)
    if master is None:
        master = ResumeMaster(user_id=user.id, tex=tex, filename=filename, revision=1)
        session.add(master)
    else:
        master.tex, master.filename = tex, filename
        master.revision += 1
    master.pdf, master.pages, master.compiled_at, master.compile_error = None, None, None, None
    await session.flush()
    await enqueue(session, TaskType.GENERATE_RESUME, {"master_id": str(master.id)}, user_id=user.id,
                  idempotency_key=f"master:{master.id}:r{master.revision}")  # fmt: skip
    return master


async def compile_master(session: AsyncSession, master: ResumeMaster, container: Container) -> None:
    try:
        result = await compile_tex(master.tex, engine=container.settings.latex_engine,
                                   time_limit=container.settings.latex_timeout_seconds)  # fmt: skip
    except LatexError as exc:
        master.compile_error = f"{exc.message}\n{exc.details.get('log', '')}".strip()
        return
    master.pdf, master.pages, master.engine = result.pdf, result.pages, result.engine
    master.compiled_at, master.compile_error = utcnow(), None


def section_summary(tex: str) -> list[dict[str, Any]]:
    """What the parser understood, so the user can see which parts will be tailored."""
    doc = parse(tex)
    out = []
    for section in doc.sections:
        item: dict[str, Any] = {"title": section.title, "role": section.role, "kind": section.kind}
        if section.kind == "entries":
            item["entries"] = [
                {"title": e.title, "bullets": len(e.items.bullets) if e.items else 0}
                for e in section.entries
            ]
        elif section.kind == "skills":
            item["lines"] = [
                {"label": line.label, "items": len(line.items)} for line in section.skills
            ]
        elif section.kind == "list" and section.listing:
            item["bullets"] = len(section.listing.bullets)
        out.append(item)
    return out


# --- requesting documents -------------------------------------------------------------------


class DocumentOptions(BaseModel):
    max_pages: int = Field(1, ge=1, le=3)
    max_projects: int | None = Field(None, ge=1, le=6)
    swap_projects: bool = True
    add_skills: bool = True
    rephrase: bool = True  # only takes effect when an LLM is configured
    tone: str = Field("professional", pattern="^(professional|warm|concise)$")


async def request_document(
    session: AsyncSession,
    user: User,
    *,
    job_id: uuid.UUID | None,
    kind: DocumentKind,
    options: DocumentOptions,
    enqueue_build: bool = True,
) -> ResumeDocument:
    """Create a document; it is built by a GENERATE_RESUME task unless the caller builds it."""
    master = await get_master(session, user.id)
    if kind == DocumentKind.RESUME and master is None:
        raise ValidationFailedError("Upload your LaTeX resume first (Resumes \u2192 Master resume)")
    title = "Resume" if kind == DocumentKind.RESUME else "Cover letter"
    if job_id is not None:
        job = await session.get(Job, job_id)
        if job is None:
            raise NotFoundError("Job not found")
        title = f"{title} \u2014 {job.title} at {job.company}"
    document = ResumeDocument(
        user_id=user.id,
        job_id=job_id,
        kind=kind,
        title=title[:300],
        options=options.model_dump(),
        master_revision=master.revision if master else None,
    )
    session.add(document)
    await session.flush()
    if enqueue_build:
        await enqueue(session, TaskType.GENERATE_RESUME, {"document_id": str(document.id)}, user_id=user.id,
                      idempotency_key=f"document:{document.id}")  # fmt: skip
    return document


# --- building -----------------------------------------------------------------------------------


@dataclass
class Context:
    user: User
    snapshot: ProfileSnapshot
    job: Job | None
    target: tailoring.JobTarget


async def _context(session: AsyncSession, document: ResumeDocument) -> Context:
    user = await session.get(User, document.user_id)
    if user is None:
        raise NotFoundError("User not found")
    profile = await get_or_create_profile(session, user)
    snapshot = await load_snapshot(session, profile)
    job = await session.get(Job, document.job_id) if document.job_id else None
    if job is not None:
        analysis = await latest_analysis(session, job.id)
        extraction = analysis.extraction if analysis else {}
        target = tailoring.JobTarget.from_extraction(
            job.title, job.company, extraction, job.description or ""
        )
    else:
        prefs = snapshot.preferences
        target = tailoring.JobTarget(
            title=" ".join(prefs.target_roles[:3]),
            company="",
            keywords=list(prefs.target_technologies),
        )
    return Context(user=user, snapshot=snapshot, job=job, target=target)


def library_projects(snapshot: ProfileSnapshot) -> list[tailoring.LibraryProject]:
    return [
        tailoring.LibraryProject(
            name=p.name,
            technologies=list(p.technologies),
            highlights=list(p.highlights),
            url=p.repository_url or p.url,
        )
        for p in snapshot.projects
        if p.verification_status == _VERIFIED and p.highlights
    ]


def verified_skills(snapshot: ProfileSnapshot) -> list[str]:
    return [
        s.name
        for s in snapshot.skills
        if s.verification_status == _VERIFIED and s.category.value != "SPOKEN_LANGUAGE"
    ]


async def build_document(
    session: AsyncSession, document_id: uuid.UUID, container: Container, *, announce: bool = True
) -> ResumeDocument:
    document = await session.get(ResumeDocument, document_id)
    if document is None:
        raise NotFoundError("Document not found")
    try:
        if document.kind == DocumentKind.RESUME:
            await _build_resume(session, document, container)
        else:
            await _build_cover_letter(session, document, container)
        document.status, document.error = DocumentStatus.READY, None
    except LatexError as exc:
        document.status = DocumentStatus.FAILED
        document.error = f"{exc.message}\n{exc.details.get('log', '')}".strip()
    await session.flush()
    if announce and document.status == DocumentStatus.READY:
        await notify(
            session,
            user_id=document.user_id,
            type=NotificationType.RESUME_READY,
            priority=NotificationPriority.NORMAL,
            title=f"{document.title} is ready",
            body=_ready_summary(document),
            job_id=document.job_id,
            action_url=f"/resumes/{document.id}",
            dedupe_key=f"document_ready:{document.id}",
            data={"document_id": str(document.id), "kind": document.kind.value},
        )
    return document


def _ready_summary(document: ResumeDocument) -> str:
    if document.kind == DocumentKind.COVER_LETTER:
        return "A cover letter written only from your verified profile."
    before, after = document.coverage_before, document.coverage_after
    if before is not None and after is not None and document.keywords_after:
        return f"Covers {round(after * 100)}% of the skills the role asks for (your master resume: {round(before * 100)}%)."
    return "Tailored from your master resume."


async def _build_resume(
    session: AsyncSession, document: ResumeDocument, container: Container
) -> None:
    master = await get_master(session, document.user_id)
    if master is None:
        raise ValidationFailedError("No master resume")
    ctx = await _context(session, document)
    opts = DocumentOptions(**(document.options or {}))
    options = tailoring.TailorOptions(
        max_projects=opts.max_projects,
        max_pages=opts.max_pages,
        swap_projects=opts.swap_projects,
        add_skills=opts.add_skills,
    )
    doc, result = tailoring.tailor(master.tex, ctx.target, library=library_projects(ctx.snapshot),
                           verified_skills=verified_skills(ctx.snapshot), options=options)  # fmt: skip
    changes = result.changes
    router = container.llm
    if opts.rephrase and ctx.job is not None and router.uses_llm(LLMTask.RESUME):
        allowed = {tailoring.canonical_key(s) for s in verified_skills(ctx.snapshot)}
        try:
            await tailoring.rephrase(doc, ctx.target, _llm_rewriter(router), allowed, changes)
        except LLMProviderError as exc:
            log.warning("resume_rephrase_failed", error=exc.message)
    scorer = tailoring.Scorer(ctx.target)
    settings = container.settings
    compiled = await compile_tex(
        doc.render(), engine=settings.latex_engine, time_limit=settings.latex_timeout_seconds
    )
    for _ in range(12):
        if compiled.pages <= options.max_pages:
            break
        change = tailoring.trim_one(doc, scorer)
        if change is None:
            break
        changes.append(change)
        compiled = await compile_tex(
            doc.render(), engine=settings.latex_engine, time_limit=settings.latex_timeout_seconds
        )
    after = tailoring.keyword_hits(doc.text, ctx.target)
    document.tex = doc.render()
    document.pdf, document.pages, document.engine = compiled.pdf, compiled.pages, compiled.engine
    document.changes = [{"kind": c.kind, "detail": c.detail} for c in changes]
    document.keywords_before = result.keywords_before
    document.keywords_after = after
    document.coverage_before = result.coverage_before
    document.coverage_after = tailoring._ratio(after)


def _llm_rewriter(router: Any) -> tailoring.Rewriter:
    class Rewrite(BaseModel):
        id: str
        text: str

    class Rewrites(BaseModel):
        items: list[Rewrite]

    async def rewrite(items: list[dict[str, str]], target: tailoring.JobTarget) -> dict[str, str]:
        wanted = ", ".join([*target.required_skills, *target.preferred_skills][:15]) or target.title
        builder = PromptBuilder(
            LLMTask.RESUME,
            """Rewrite each resume bullet so its wording lines up with the job, without changing any facts.
Rules: keep every number exactly; do not add tools, skills, companies, metrics or outcomes that are not
in the bullet; keep the same length (plus or minus 20%); start with a strong past-tense verb; British
spelling; no first person. If a bullet cannot be improved truthfully, return it unchanged.
Return {"items": [{"id": ..., "text": ...}]} with every id.""",
        )
        builder.trusted(
            "JOB TERMS TO MIRROR WHERE TRUTHFUL", f"Role: {target.title}\nSkills: {wanted}"
        )
        builder.trusted("BULLETS", "\n".join(f"{item['id']}: {item['text']}" for item in items))
        response = await router.structured(
            builder.build(max_tokens=1600, temperature=0.2), Rewrites
        )
        return {item.id: item.text for item in response.items}

    return rewrite


# --- cover letters ------------------------------------------------------------------------------


def _first_lower(text: str) -> str:
    text = text.strip().rstrip(".")
    if len(text) > 1 and text[0].isupper() and not text[1].isupper():
        return text[0].lower() + text[1:]
    return text


@dataclass
class Story:
    context: str
    text: str
    score: float
    kind: str
    # Canonical skills this story demonstrates: named in the text or in the item's tech stack.
    skills: frozenset[str] = frozenset()
    # Only the skills the text itself names ("Built the dashboard in React").
    named: frozenset[str] = frozenset()


def _skills_of(text: str, technologies: list[str]) -> frozenset[str]:
    names = [*extract_skill_names(text), *technologies]
    return frozenset(tailoring.canonical_key(normalize_skill_name(n)) for n in names)


def _named_in(text: str) -> frozenset[str]:
    return frozenset(tailoring.canonical_key(n) for n in extract_skill_names(text))


def evidence_stories(snapshot: ProfileSnapshot, target: tailoring.JobTarget) -> list[Story]:
    """Verified achievements phrased as first-person evidence, most relevant first."""
    scorer = tailoring.Scorer(target)
    stories: list[Story] = []
    for exp in snapshot.experience:
        if exp.verification_status != _VERIFIED:
            continue
        context = (
            f"at {exp.organization}"
            if "intern" in exp.role.lower()
            else f"as {exp.role} at {exp.organization}"
        )
        for text in exp.achievements:
            stories.append(
                Story(
                    context,
                    text,
                    scorer.score(text + " " + " ".join(exp.technologies)) + 1.0,
                    "experience",
                    _skills_of(text, exp.technologies),
                    _named_in(text),
                )
            )
    for project in snapshot.projects:
        if project.verification_status != _VERIFIED:
            continue
        name = project.name.split(":")[0].strip()
        for text in project.highlights:
            stories.append(
                Story(
                    f"on {name}",
                    text,
                    scorer.score(text + " " + " ".join(project.technologies)),
                    "project",
                    _skills_of(text, project.technologies),
                    _named_in(text),
                )
            )
    stories.sort(key=lambda s: -s.score)
    return stories


def _studying(education: Any) -> str:
    """'I am a final-year B.Tech student in CS at X' or 'I am studying for a ... graduating in 2028'."""
    field = f" in {education.field}" if education.field else ""
    end = education.end_date
    if end is not None:
        months_left = (end.year - utcnow().year) * 12 + (end.month - utcnow().month)
        if 0 <= months_left <= 12:
            return f"I am a final-year {education.degree} student{field} at {education.institution}"
        if months_left > 12:
            return f"I am studying for a {education.degree}{field} at {education.institution}, graduating in {end.year}"
        return f"I graduated with a {education.degree}{field} from {education.institution}"
    if education.is_current:
        return f"I am studying for a {education.degree}{field} at {education.institution}"
    return f"I hold a {education.degree}{field} from {education.institution}"


def _and_list(items: list[str]) -> str:
    return items[0] if len(items) == 1 else f"{', '.join(items[:-1])} and {items[-1]}"


def student_phrase(education: Any) -> str:
    """'a final-year B.Tech student at IIIT-Delhi', 'a B.Tech student at X' or 'a B.Tech graduate of X'."""
    school = (
        education.institution.split("(")[-1].rstrip(")")
        if "(" in education.institution
        else education.institution
    )
    end = education.end_date
    if end is not None:
        months_left = (end.year - utcnow().year) * 12 + (end.month - utcnow().month)
        if 0 <= months_left <= 12:
            return f"a final-year {education.degree} student at {school}"
        if months_left < 0:
            return f"a {education.degree} graduate of {school}"
    return f"a {education.degree} student at {school}"


def cover_letter_text(
    snapshot: ProfileSnapshot, target: tailoring.JobTarget, tone: str = "professional"
) -> list[str]:
    basics = snapshot.profile
    education = next((e for e in snapshot.education if e.verification_status == _VERIFIED), None)
    orgs = [
        e.organization
        for e in snapshot.experience
        if e.verification_status == _VERIFIED and "intern" in e.role.lower()
    ]
    role = f"the {target.title} role" + (f" at {target.company}" if target.company else "")
    intro = f"I am writing to apply for {role}."
    if education:
        intro += f" {_studying(education)}"
        intro += f", with internships at {' and '.join(orgs[:2])}." if orgs else "."
    stories = evidence_stories(snapshot, target)
    picked, seen_contexts = [], set()
    for story in stories:
        if story.context in seen_contexts:
            continue
        picked.append(story)
        seen_contexts.add(story.context)
        if len(picked) == 3:
            break
    evidence = " ".join(
        f"{s.context[0].upper()}{s.context[1:]}, I {_first_lower(s.text)}." for s in picked
    )
    skills = [
        s
        for s in verified_skills(snapshot)
        if tailoring.canonical_key(s) in tailoring.Scorer(target).skills
    ]
    skills_line = ""
    if skills:
        # Only claim what is verifiably true: these are skills on the user's verified profile.
        skills_line = f"My skills include {_and_list(skills[:5])}, which this role asks for."
    company = target.company or "your team"
    closing = {
        "warm": f"I would love the chance to bring this energy to {company}. Thank you for considering my application; I would be glad to talk about how I can help.",
        "concise": f"I would welcome a conversation about how I can contribute to {company}. Thank you for your time.",
    }.get(
        tone,
        f"I would welcome the opportunity to discuss how I can contribute to {company}. Thank you for your time and consideration.",
    )
    paragraphs = [intro, evidence, skills_line, closing]
    if basics.full_name:
        paragraphs.append(basics.full_name)
    return [p for p in paragraphs if p]


def cover_letter_tex(
    master_tex: str | None, snapshot: ProfileSnapshot, paragraphs: list[str], company: str
) -> str:
    """A letter that shares the master resume's fonts and header (letterhead), or a clean default."""
    body_paragraphs = (
        paragraphs[:-1]
        if snapshot.profile.full_name and paragraphs[-1] == snapshot.profile.full_name
        else paragraphs
    )
    today = utcnow().strftime("%d %B %Y").lstrip("0")
    greeting = f"Dear Hiring Team at {escape(company)}," if company else "Dear Hiring Team,"
    letter = (
        f"\\vspace{{10pt}}\n{today}\n\n\\vspace{{8pt}}\n{greeting}\n\n\\vspace{{4pt}}\n"
        + "\n\n\\vspace{4pt}\n".join(escape(p) for p in body_paragraphs)
        + f"\n\n\\vspace{{10pt}}\nSincerely,\\\\[2pt]\n{escape(snapshot.profile.full_name or '')}\n"
    )
    if master_tex:
        doc = parse(master_tex)
        begin = doc.preamble.find("\\begin{document}")
        header = doc.preamble[begin:]
        head = doc.preamble[:begin]
        return head + header + "\n\\setlength{\\parskip}{6pt}\n" + letter + "\n\\end{document}\n"
    return (
        "\\documentclass[a4paper,11pt]{article}\n\\usepackage[margin=1in]{geometry}\n\\usepackage{charter}\n"
        "\\setlength{\\parindent}{0pt}\n\\setlength{\\parskip}{6pt}\n\\pagestyle{empty}\n\\begin{document}\n"
        + letter
        + "\\end{document}\n"
    )


async def _build_cover_letter(
    session: AsyncSession, document: ResumeDocument, container: Container
) -> None:
    ctx = await _context(session, document)
    opts = DocumentOptions(**(document.options or {}))
    paragraphs = cover_letter_text(ctx.snapshot, ctx.target, opts.tone)
    master = await get_master(session, document.user_id)
    tex = cover_letter_tex(
        master.tex if master else None, ctx.snapshot, paragraphs, ctx.target.company
    )
    settings = container.settings
    compiled = await compile_tex(
        tex, engine=settings.latex_engine, time_limit=settings.latex_timeout_seconds
    )
    document.tex, document.body = tex, "\n\n".join(paragraphs)
    document.pdf, document.pages, document.engine = compiled.pdf, compiled.pages, compiled.engine
    document.changes = [
        {"kind": "grounded", "detail": "Every sentence comes from your verified profile"}
    ]


# --- signed download links ------------------------------------------------------------------------


def sign_download(secret: str, document_id: uuid.UUID, ttl_seconds: int = 900) -> str:
    expires = int(time.time()) + ttl_seconds
    payload = f"{document_id}.{expires}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{expires}.{signature}"


def verify_download(secret: str, document_id: uuid.UUID, token: str) -> bool:
    match = re.fullmatch(r"(\d+)\.([0-9a-f]{32})", token or "")
    if not match or int(match.group(1)) < time.time():
        return False
    expected = hmac.new(
        secret.encode(), f"{document_id}.{match.group(1)}".encode(), hashlib.sha256
    ).hexdigest()[:32]
    return hmac.compare_digest(expected, match.group(2))


def pdf_filename(document: ResumeDocument, full_name: str | None) -> str:
    who = re.sub(r"[^A-Za-z0-9]+", "_", full_name or "Resume").strip("_") or "Resume"
    what = "Resume" if document.kind == DocumentKind.RESUME else "Cover_Letter"
    job = ""
    if " at " in document.title:
        job = (
            "_" + re.sub(r"[^A-Za-z0-9]+", "_", document.title.rsplit(" at ", 1)[1]).strip("_")[:40]
        )
    return f"{who}_{what}{job}.pdf"


def plain(tex: str) -> str:
    return plain_text(tex)
