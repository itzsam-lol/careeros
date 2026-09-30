"""Interview preparation and outreach drafts, built only from verified profile facts.

Nothing here is sent anywhere: drafts are returned to the user to edit, copy and send themselves.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass

from careeros.intelligence.skills import canonical_key, lookup
from careeros.profile.enums import VerificationStatus
from careeros.profile.service import ProfileSnapshot
from careeros.resumes import tailor as tailoring
from careeros.resumes.service import evidence_stories, student_phrase, verified_skills

_VERIFIED = VerificationStatus.VERIFIED


@dataclass
class TalkingPoint:
    topic: str
    status: str  # STRONG | RELATED | GAP
    evidence: list[str]
    tip: str


@dataclass
class StoryPrompt:
    question: str
    story: str
    where: str


def _display(name: str) -> str:
    skill = lookup(name)
    return skill.name if skill else name


def interview_prep(snapshot: ProfileSnapshot, target: tailoring.JobTarget) -> dict[str, object]:
    stories = evidence_stories(snapshot, target)
    mine = {canonical_key(s) for s in verified_skills(snapshot)}
    topics = list(dict.fromkeys([*target.required_skills, *target.preferred_skills]))[:8]
    points: list[TalkingPoint] = []
    for topic in topics:
        key = canonical_key(_display(topic))
        # Quote achievements that name the skill; for items that only list it in their tech
        # stack, name the item rather than quoting an unrelated bullet from it.
        evidence = [f"{s.context}: {s.text}" for s in stories if key in s.named][:2]
        for context in dict.fromkeys(
            s.context for s in stories if key in s.skills and key not in s.named
        ):
            if len(evidence) >= 2:
                break
            evidence.append(f"{context}: built with {_display(topic)}")
        if evidence:
            points.append(TalkingPoint(_display(topic), "STRONG", evidence,
                                       f"Walk through one example end to end: the problem, what you built with {_display(topic)}, and the result."))  # fmt: skip
        elif key in mine:
            points.append(TalkingPoint(_display(topic), "RELATED", [],
                                       f"{_display(topic)} is on your profile but not in a highlighted achievement; prepare a concrete example of using it."))  # fmt: skip
        else:
            points.append(TalkingPoint(_display(topic), "GAP", [],
                                       f"Not on your profile. Be honest, show adjacent experience, and explain how you would ramp up on {_display(topic)}."))  # fmt: skip

    def find(
        pattern: str, kinds: tuple[str, ...] = ("experience", "project")
    ) -> StoryPrompt | None:
        for story in stories:
            if story.kind in kinds and re.search(pattern, story.text, re.I):
                return StoryPrompt("", story.text, story.context)
        return None

    behavioural: list[StoryPrompt] = []
    for question, pattern in (
        ("Tell me about a project you are proud of.", r"\d"),
        (
            "Describe a hard problem you debugged or investigated.",
            r"root cause|investigat|debug|isolat",
        ),
        (
            "Tell me about a time you automated or improved a process.",
            r"automat|faster|improv|reproduc",
        ),
        (
            "How do you explain technical work to non-technical people?",
            r"present|explain|non-technical|walkthrough",
        ),
        (
            "Tell me about working with users or stakeholders.",
            r"field|users|shop owners|survey|customers|students",
        ),
    ):
        prompt = find(pattern)
        if prompt:
            prompt.question = question
            behavioural.append(prompt)
    leadership = [
        a
        for a in snapshot.achievements
        if a.verification_status == _VERIFIED and a.kind.value in ("LEADERSHIP", "TEACHING")
    ]
    if leadership:
        top = leadership[0]
        behavioural.append(
            StoryPrompt(
                "Tell me about a time you led people.",
                top.description or top.title,
                top.organization or "",
            )
        )

    ask = [
        f"What does success look like in the first six months for this {target.title or 'role'}?"
    ]
    for responsibility in target.responsibilities[:3]:
        short = responsibility.rstrip(".")
        ask.append(f"How does the team approach “{short[:90]}” today, and where would I start?")
    ask.append("What do new graduates who do well here have in common?")
    return {
        "talking_points": [asdict(p) for p in points],
        "behavioural": [asdict(b) for b in behavioural],
        "questions_to_ask": ask,
        "summary": {
            "strong": sum(p.status == "STRONG" for p in points),
            "related": sum(p.status == "RELATED" for p in points),
            "gaps": sum(p.status == "GAP" for p in points),
        },
    }


def outreach_drafts(
    snapshot: ProfileSnapshot, target: tailoring.JobTarget, job_url: str | None
) -> list[dict[str, str]]:
    profile = snapshot.profile
    name = profile.full_name or "I"
    education = next((e for e in snapshot.education if e.verification_status == _VERIFIED), None)
    who = student_phrase(education) if education else (profile.headline or "a candidate")
    stories = evidence_stories(snapshot, target)
    best = stories[0] if stories else None
    hook = ""
    if best:
        hook = f" {best.context[0].upper()}{best.context[1:]}, I {best.text[0].lower()}{best.text[1:].rstrip('.')}."
    role = target.title or "the open role"
    company = target.company or "your company"
    link = f"\n\nJob posting: {job_url}" if job_url else ""
    connection = f"Hi, I'm {name}, {who}. I'm applying for the {role} role at {company} and would value a quick chat about the team. Thank you!"
    if len(connection) > 300:
        connection = f"Hi, I'm {name}. I'm applying for the {role} role at {company} and would value a quick chat. Thank you!"
    signature = "\n".join(
        filter(None, [name, profile.contact_email, profile.phone, profile.linkedin_url])
    )
    referral = (
        f"Hi,\n\nI'm {name}, {who}. I'm applying for the {role} role at {company} and wanted to ask whether you "
        f"would be comfortable referring me, or pointing me to the right person.{hook}\n\n"
        f"I've attached my resume. Happy to share anything else that helps.{link}\n\nThanks so much,\n{signature}"
    )
    follow_up = (
        f"Hi,\n\nI applied for the {role} role at {company} recently and wanted to reiterate my interest.{hook}\n\n"
        f"I'd be glad to share more about my work if helpful. Thank you for your time.\n\nBest regards,\n{signature}"
    )
    thank_you = (
        f"Hi,\n\nThank you for taking the time to speak with me about the {role} role at {company}. I enjoyed learning "
        f"about the team and I'm even more excited about the opportunity.\n\nBest regards,\n{name}"
    )
    return [
        {
            "kind": "connection_note",
            "title": "LinkedIn connection note",
            "subject": "",
            "body": connection,
        },
        {
            "kind": "referral_request",
            "title": "Referral request",
            "subject": f"Referral for {role} at {company}",
            "body": referral,
        },
        {
            "kind": "follow_up",
            "title": "Follow-up after applying",
            "subject": f"Following up: {role} application",
            "body": follow_up,
        },
        {
            "kind": "thank_you",
            "title": "Thank-you after an interview",
            "subject": f"Thank you — {role}",
            "body": thank_you,
        },
    ]
