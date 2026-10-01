"""Job function from the title: engineering and data roles vs. sales, support, HR, legal...

The domain classifier reads the whole posting, so a sales role at an AI company still looks
like "ML/AI". The title says what the person actually does all day.
"""

from __future__ import annotations

import re
from enum import StrEnum


class JobFunction(StrEnum):
    ENGINEERING = "ENGINEERING"  # software
    HARDWARE = "HARDWARE"  # electrical, circuit, mechanical and facilities engineering
    DATA = "DATA"  # data science, analytics, ML and AI
    RESEARCH = "RESEARCH"
    PRODUCT = "PRODUCT"
    DESIGN = "DESIGN"
    SALES = "SALES"
    MARKETING = "MARKETING"
    CUSTOMER = "CUSTOMER"
    PEOPLE = "PEOPLE"
    LEGAL = "LEGAL"
    FINANCE = "FINANCE"
    OPERATIONS = "OPERATIONS"


LABELS = {
    JobFunction.ENGINEERING: "software engineering",
    JobFunction.HARDWARE: "hardware engineering",
    JobFunction.DATA: "data and AI",
    JobFunction.RESEARCH: "research",
    JobFunction.PRODUCT: "product management",
    JobFunction.DESIGN: "design",
    JobFunction.SALES: "sales",
    JobFunction.MARKETING: "marketing",
    JobFunction.CUSTOMER: "customer support and success",
    JobFunction.PEOPLE: "HR and recruiting",
    JobFunction.LEGAL: "legal and compliance",
    JobFunction.FINANCE: "finance and accounting",
    JobFunction.OPERATIONS: "operations",
}


def _words(*terms: str) -> re.Pattern[str]:
    return re.compile(r"(?<![a-z0-9])(?:" + "|".join(terms) + r")(?![a-z0-9])")


# Unambiguous data/ML titles win over everything ("Sales Data Analyst" is an analyst).
_STRONG_DATA = _words(
    r"data scien\w*", r"data analy\w*", r"data engineer\w*", r"analytics", r"machine learning",
    r"deep learning", r"quant", r"quants", r"quantitative", r"statistic\w*", r"business intelligence",
    r"decision scien\w*", r"mlops",
)  # fmt: skip
# Functions whose people are not building software even when "engineer" is in the title
# ("Sales Engineer", "Customer Success Engineer").
_DOMINANT: list[tuple[JobFunction, re.Pattern[str]]] = [
    (JobFunction.SALES, _words(
        r"sales", r"pre-?sales", r"account executive", r"account manager", r"account director",
        r"business development", r"bd", r"bdr", r"sdr", r"territory", r"key accounts?", r"client partner",
        r"partner(?:ship)?s? (?:manager|lead|director)", r"channel (?:manager|sales|partner)",
        r"inside sales", r"commercial (?:manager|lead|director|executive)",
        r"partner(?:ship)?s? leader", r"field partner", r"alliances?", r"solutions? consultant",
        r"go-to-market", r"gtm",
    )),
    (JobFunction.CUSTOMER, _words(
        r"customer success", r"customer support", r"customer service", r"customer experience",
        r"client success", r"client services?", r"technical support", r"help ?desk", r"service desk",
        r"support (?:specialist|associate|representative|agent|executive|analyst)",
        r"implementation (?:specialist|consultant|manager|lead)", r"onboarding (?:specialist|manager)",
    )),
    (JobFunction.PEOPLE, _words(
        r"recruit\w*", r"talent (?:acquisition|partner|sourcer|management)", r"sourcer",
        r"human resources", r"hr", r"hrbp", r"people (?:partner|operations|ops|business partner|team)",
        r"payroll", r"learning (?:and|&) development",
    )),
    (JobFunction.LEGAL, _words(
        r"legal", r"counsel", r"attorney", r"lawyer", r"paralegal", r"compliance", r"privacy officer",
        r"contracts? manager",
    )),
    (JobFunction.MARKETING, _words(
        r"marketing", r"marketer", r"brand", r"seo", r"copywriter", r"communications", r"public relations",
        r"social media", r"community manager", r"demand gen\w*", r"content (?:writer|strategist|manager)",
        r"events? (?:manager|coordinator)",
    )),
    # Chip, electrical and plant engineering: "engineer" in the title, but not software.
    (JobFunction.HARDWARE, _words(
        r"electrical", r"electronics?", r"circuit", r"layout", r"analog", r"mixed[- ]signal",
        r"digital design", r"asic", r"fpga", r"vlsi", r"rtl", r"physical design",
        r"design verification", r"silicon", r"semiconductor", r"mechanical", r"civil",
        r"facilities", r"manufacturing", r"process engineer\w*", r"equipment", r"hardware",
        r"pcb", r"yield", r"packaging", r"signal integrity", r"hbm", r"dram", r"nand",
        r"memory (?:circuit|design|product)",
    )),
]  # fmt: skip
# "Electronics Software Engineer" still writes software.
_SOFTWARE = _words(r"software", r"firmware", r"sde", r"swe")
_TECH: list[tuple[JobFunction, re.Pattern[str]]] = [
    (JobFunction.ENGINEERING, _words(
        r"engineer\w*", r"developer", r"development", r"sde", r"swe", r"sdet", r"programmer",
        r"software", r"devops", r"sre", r"site reliability", r"architect", r"firmware", r"full[- ]?stack",
        r"back[- ]?end", r"front[- ]?end", r"mobile", r"android", r"ios", r"qa", r"quality assurance",
        r"tester", r"testing", r"technologist", r"computer scientist", r"tech lead", r"cto",
        r"infrastructure", r"platform", r"security analyst", r"cyber\w*",
    )),
    (JobFunction.RESEARCH, _words(r"research\w*", r"scientist", r"phd", r"postdoc\w*")),
]  # fmt: skip
_WEAK_DATA = _words(
    r"ai", r"ml", r"llms?", r"nlp", r"genai", r"generative ai", r"artificial intelligence",
    r"computer vision", r"agentic",
)  # fmt: skip
# Functions that only win when nothing technical is in the title ("Finance Systems Engineer"
# is an engineer, "Operations Research" is research).
_SOFT: list[tuple[JobFunction, re.Pattern[str]]] = [
    (JobFunction.FINANCE, _words(
        r"accountant", r"accounting", r"accounts (?:payable|receivable)", r"finance", r"financial",
        r"fp&a", r"controller", r"audit\w*", r"tax", r"treasury", r"billing", r"underwriter",
        r"actuar\w*", r"credit (?:analyst|risk)",
    )),
    (JobFunction.OPERATIONS, _words(
        r"operations", r"ops", r"program manager", r"project manager", r"programme manager",
        r"supply chain", r"logistics", r"procurement", r"facilities", r"office manager",
        r"executive assistant", r"administrative", r"administrator", r"receptionist", r"coordinator",
        r"general manager", r"country manager", r"managing director", r"warehouse", r"technician",
        r"driver",
    )),
]  # fmt: skip
_PRODUCT = _words(
    r"product manager", r"product owner", r"product lead", r"product management", r"head of product",
    r"product director", r"group product manager",
)  # fmt: skip
_DESIGN = _words(r"designer", r"ux", r"ui/ux", r"user experience", r"design lead", r"visual design")
_ANALYST = _words(r"analyst", r"analysts")
# "/" joins alternatives ("AI/ML Engineer", "UI/UX Designer"), so it does not split segments.
_SEGMENTS = re.compile(r"\s*(?:[,(|:–—]|\s-\s|\))\s*")


def _segment_functions(segment: str) -> set[JobFunction]:
    tech = {function for function, pattern in _TECH if pattern.search(segment)}
    if _STRONG_DATA.search(segment):
        return {JobFunction.DATA, *tech}
    for function, pattern in _DOMINANT:
        if function is JobFunction.HARDWARE and _SOFTWARE.search(segment):
            continue
        if pattern.search(segment):
            return {function}
    if tech:
        return tech | ({JobFunction.DATA} if _WEAK_DATA.search(segment) else set())
    for function, pattern in _SOFT:
        if pattern.search(segment):
            return {function}
    if _PRODUCT.search(segment):
        return {JobFunction.PRODUCT}
    if _DESIGN.search(segment):
        return {JobFunction.DESIGN}
    if _WEAK_DATA.search(segment) or _ANALYST.search(segment):
        return {JobFunction.DATA}
    return set()


# A bare role noun ("Engineer", "Senior Analyst II") says less than the specialty after it:
# "ENGINEER, SIG ELECTRICAL DESIGN", "Analyst, Algorithm Research".
_GENERIC = re.compile(
    r"^(?:(?:senior|sr|staff|principal|lead|junior|jr|associate|intern)\s+)*"
    r"(?:engineer|analyst|developer|scientist|specialist|associate|consultant)"
    r"(?:\s+(?:i{1,3}|iv|[1-5]))?$"
)


def title_functions(title: str) -> set[JobFunction]:
    """Functions named by the first part of the title that names any (empty if unclear).

    "Strategic Account Executive - Turkey" -> {SALES}; "Machine Learning Engineer" ->
    {DATA, ENGINEERING}; "Binance Accelerator Program - AI Engineer" -> {ENGINEERING, DATA}.
    """
    segments = [s for s in _SEGMENTS.split(title.lower()) if s]
    for index, segment in enumerate(segments):
        found = _segment_functions(segment)
        if not found:
            continue
        if _GENERIC.match(segment):
            for later in segments[index + 1 :]:
                specific = _segment_functions(later)
                if specific:
                    return specific
        return found
    return set()
