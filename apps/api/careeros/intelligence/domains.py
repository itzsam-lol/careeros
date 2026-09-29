"""Coarse job-domain classification (used for matching and analytics)."""

from __future__ import annotations

import re
from enum import StrEnum


class JobDomain(StrEnum):
    ML_AI = "ML_AI"
    RESEARCH = "RESEARCH"
    BACKEND = "BACKEND"
    FRONTEND = "FRONTEND"
    FULL_STACK = "FULL_STACK"
    DATA = "DATA"
    DEVOPS = "DEVOPS"
    SECURITY = "SECURITY"
    MOBILE = "MOBILE"
    EMBEDDED = "EMBEDDED"
    PRODUCT = "PRODUCT"
    DESIGN = "DESIGN"
    OTHER = "OTHER"


_KEYWORDS: dict[JobDomain, tuple[str, ...]] = {
    JobDomain.ML_AI: (
        "machine learning", "deep learning", "ml", "ai", "artificial intelligence", "nlp",
        "computer vision", "llm", "large language model", "pytorch", "tensorflow", "neural",
        "model training", "generative", "rag", "transformer", "reinforcement learning", "mlops",
    ),
    JobDomain.RESEARCH: (
        "research", "researcher", "publication", "paper", "phd", "lab", "postdoc",
        "research assistant", "scientist", "experiments",
    ),
    JobDomain.BACKEND: (
        "backend", "back-end", "api", "apis", "microservices", "server", "distributed systems",
        "database", "fastapi", "django", "spring", "node.js", "golang", "java",
    ),
    JobDomain.FRONTEND: (
        "frontend", "front-end", "react", "vue", "angular", "css", "ui", "web app", "next.js",
        "typescript", "accessibility",
    ),
    JobDomain.FULL_STACK: ("full stack", "full-stack", "fullstack"),
    JobDomain.DATA: (
        "data analyst", "data engineer", "analytics", "etl", "sql", "dashboard", "tableau",
        "power bi", "data pipeline", "warehouse", "bigquery", "spark", "statistics",
    ),
    JobDomain.DEVOPS: (
        "devops", "sre", "site reliability", "kubernetes", "terraform", "infrastructure",
        "ci/cd", "observability", "cloud platform", "on-call",
    ),
    JobDomain.SECURITY: ("security", "penetration", "appsec", "vulnerability", "soc", "threat"),
    JobDomain.MOBILE: ("android", "ios", "mobile", "flutter", "react native", "swift", "kotlin"),
    JobDomain.EMBEDDED: ("embedded", "firmware", "robotics", "ros", "fpga", "hardware", "rtos"),
    JobDomain.PRODUCT: ("product manager", "product management", "roadmap", "stakeholders"),
    JobDomain.DESIGN: ("designer", "ux", "user experience", "figma", "visual design"),
}  # fmt: skip

_PATTERNS = {
    domain: [re.compile(rf"(?<![\w-]){re.escape(word)}(?![\w-])", re.IGNORECASE) for word in words]
    for domain, words in _KEYWORDS.items()
}


def domain_scores(title: str, text: str) -> dict[JobDomain, float]:
    scores: dict[JobDomain, float] = {}
    for domain, patterns in _PATTERNS.items():
        score = 0.0
        for pattern in patterns:
            score += 3.0 * len(pattern.findall(title)) + min(4, len(pattern.findall(text))) * 0.5
        if score:
            scores[domain] = score
    return scores


def classify_domain(title: str, text: str) -> tuple[JobDomain, bool]:
    """(primary domain, is_research). Title evidence dominates body evidence."""
    scores = domain_scores(title, text)
    if not scores:
        return JobDomain.OTHER, False
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    primary = ranked[0][0]
    research_score = scores.get(JobDomain.RESEARCH, 0.0)
    is_research = (
        bool(re.search(r"\bresearch\b", title, re.I)) or research_score >= 0.6 * ranked[0][1]
    )
    if primary == JobDomain.RESEARCH and len(ranked) > 1:
        # "AI Research Intern" is an ML role with a research flavour.
        primary = ranked[1][0]
    if JobDomain.FULL_STACK in scores and primary in (JobDomain.BACKEND, JobDomain.FRONTEND):
        primary = JobDomain.FULL_STACK
    return primary, is_research


def domains_for_text(text: str) -> set[JobDomain]:
    """Domains a free-text phrase (e.g. a target role) belongs to."""
    scores = domain_scores(text, "")
    return {domain for domain, score in scores.items() if score > 0}
