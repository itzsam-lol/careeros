"""Normalisation of heterogeneous postings into the canonical job shape (spec §14)."""

from __future__ import annotations

import hashlib
import html
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from bs4 import BeautifulSoup

from careeros.core.clock import ensure_aware
from careeros.core.enums import CompensationPeriod, EmploymentType, RemoteType, SeniorityLevel
from careeros.discovery.raw import RawJob
from careeros.jobs.models import ApplicationPlatform

# --- text ---------------------------------------------------------------------------------------

_BLOCK_TAGS = (
    "p",
    "div",
    "br",
    "li",
    "ul",
    "ol",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "tr",
    "section",
)


def html_to_text(markup: str) -> str:
    """Readable plain text from job-description HTML (bullets kept, scripts dropped)."""
    if "&lt;" in markup and "<" not in markup.replace("&lt;", ""):
        markup = html.unescape(markup)  # Greenhouse returns entity-escaped HTML
    soup = BeautifulSoup(markup, "lxml")
    for tag in soup(["script", "style", "noscript", "iframe", "svg", "form"]):
        tag.decompose()
    for li in soup.find_all("li"):
        li.insert_before("\n• ")
    for tag in soup.find_all(_BLOCK_TAGS):
        tag.insert_after("\n")
    text = soup.get_text()
    lines = [" ".join(line.split()) for line in text.splitlines()]
    cleaned: list[str] = []
    for line in lines:
        if line or (cleaned and cleaned[-1]):
            cleaned.append(line)
    return "\n".join(cleaned).strip()


def clean_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r", "").splitlines()]
    return re.sub(r"\n{3,}", "\n\n", "\n".join(lines)).strip()


def description_hash(text: str) -> str:
    normalized = re.sub(r"https?://\S+", "", text.lower())
    normalized = re.sub(r"[^a-z0-9]+", " ", normalized).strip()
    return hashlib.sha256(normalized.encode()).hexdigest()


def shingles(text: str, size: int = 5) -> set[str]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < size:
        return {" ".join(words)} if words else set()
    return {" ".join(words[i : i + size]) for i in range(len(words) - size + 1)}


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


# --- URLs -----------------------------------------------------------------------------------------

_TRACKING_PARAMS = frozenset(
    {
        "gh_src", "lever-source", "lever-origin", "lever-source[]", "source", "src", "ref",
        "referrer", "trk", "trackingid", "fbclid", "gclid", "mc_cid", "mc_eid", "_hsenc", "_hsmi",
        "iis", "iisn", "ccuid", "jobboard", "utm", "campaign", "medium",
    }
)  # fmt: skip


def canonicalize_url(url: str | None) -> str | None:
    if not url:
        return None
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return None
    if parts.scheme not in ("http", "https") or not parts.hostname:
        return None
    host = parts.hostname.lower()
    port = f":{parts.port}" if parts.port and parts.port not in (80, 443) else ""
    query = sorted(
        (k, v)
        for k, v in parse_qsl(parts.query, keep_blank_values=False)
        if not k.lower().startswith("utm_") and k.lower() not in _TRACKING_PARAMS
    )
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    if len(path) > 1:
        path = path.rstrip("/")
    return urlunsplit(("https", f"{host}{port}", path, urlencode(query), ""))[:1000]


_PLATFORM_HOSTS: list[tuple[re.Pattern[str], ApplicationPlatform]] = [
    (re.compile(r"(^|\.)greenhouse\.io$"), ApplicationPlatform.GREENHOUSE),
    (re.compile(r"(^|\.)lever\.co$"), ApplicationPlatform.LEVER),
    (re.compile(r"(^|\.)ashbyhq\.com$"), ApplicationPlatform.ASHBY),
    (re.compile(r"(^|\.)(myworkdayjobs|myworkdaysite|workday)\.com$"), ApplicationPlatform.WORKDAY),
    (re.compile(r"(^|\.)smartrecruiters\.com$"), ApplicationPlatform.SMARTRECRUITERS),
    (re.compile(r"(^|\.)workable\.com$"), ApplicationPlatform.WORKABLE),
    (re.compile(r"(^|\.)icims\.com$"), ApplicationPlatform.ICIMS),
    (re.compile(r"(^|\.)taleo\.net$"), ApplicationPlatform.TALEO),
    (re.compile(r"(^|\.)linkedin\.com$"), ApplicationPlatform.LINKEDIN),
    (re.compile(r"^forms\.gle$"), ApplicationPlatform.GOOGLE_FORMS),
]


def detect_platform(url: str | None) -> ApplicationPlatform:
    if not url:
        return ApplicationPlatform.UNKNOWN
    if url.startswith("mailto:"):
        return ApplicationPlatform.EMAIL
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    if host == "docs.google.com" and parts.path.startswith("/forms"):
        return ApplicationPlatform.GOOGLE_FORMS
    for pattern, platform in _PLATFORM_HOSTS:
        if pattern.search(host):
            return platform
    return ApplicationPlatform.GENERIC if host else ApplicationPlatform.UNKNOWN


# --- names, titles, locations ----------------------------------------------------------------------

_COMPANY_SUFFIXES = re.compile(
    r"\b(inc|incorporated|llc|l\.l\.c|ltd|limited|pvt|private|corp|corporation|co|company|gmbh|plc|"
    r"s\.a|sa|ag|bv|b\.v|pte|pty|srl|oy|ab)\b\.?",
    re.IGNORECASE,
)


def normalize_company(name: str) -> str:
    value = name.lower().replace("&", " and ")
    value = _COMPANY_SUFFIXES.sub(" ", value)
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


_TITLE_REPLACEMENTS = [
    (re.compile(r"\bsr\b\.?"), "senior"),
    (re.compile(r"\bjr\b\.?"), "junior"),
    (re.compile(r"\bswe\b"), "software engineer"),
    (re.compile(r"\bsde\b"), "software development engineer"),
    (re.compile(r"\bml\b"), "machine learning"),
    (re.compile(r"\bai\b"), "artificial intelligence"),
    (re.compile(r"\beng\b"), "engineer"),
    (re.compile(r"\bmgr\b"), "manager"),
]


def normalize_title(title: str) -> str:
    value = title.lower()
    value = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", value)  # (Remote), [R-1234], (m/f/d)
    # Requisition ids need an explicit marker so words like "Identity" survive.
    value = re.sub(
        r"\b(?:req(?:uisition)?|job)\s*(?:id|no\.?|number)?\s*[:#]\s*[a-z0-9-]+", " ", value
    )
    value = re.sub(r"#\s*\d+|\br-?\d{3,}\b", " ", value)
    value = value.replace("&", " and ")
    for pattern, replacement in _TITLE_REPLACEMENTS:
        value = pattern.sub(replacement, value)
    value = re.sub(r"[^a-z0-9+#]+", " ", value)
    return " ".join(value.split())[:300]


_CITY_SYNONYMS = {
    "bangalore": "bengaluru",
    "gurgaon": "gurugram",
    "bombay": "mumbai",
    "new delhi": "delhi",
    "madras": "chennai",
    "calcutta": "kolkata",
    "nyc": "new york",
    "new york city": "new york",
    "sf": "san francisco",
    "bay area": "san francisco",
}


def normalize_location(location: str) -> str:
    value = location.lower()
    for synonym, canonical in _CITY_SYNONYMS.items():
        value = re.sub(rf"\b{re.escape(synonym)}\b", canonical, value)
    parts = sorted(
        {" ".join(re.sub(r"[^a-z0-9]+", " ", p).split()) for p in re.split(r"[;/|]", value)}
    )
    return "; ".join(p for p in parts if p)[:300]


_COUNTRY_ALIASES: dict[str, str] = {
    "india": "India", "united states": "United States", "united states of america": "United States",
    "usa": "United States", "u.s.": "United States", "us": "United States",
    "united kingdom": "United Kingdom", "uk": "United Kingdom", "england": "United Kingdom",
    "canada": "Canada", "germany": "Germany", "deutschland": "Germany", "singapore": "Singapore",
    "netherlands": "Netherlands", "france": "France", "ireland": "Ireland",
    "switzerland": "Switzerland", "japan": "Japan", "australia": "Australia",
    "united arab emirates": "United Arab Emirates", "uae": "United Arab Emirates",
    "israel": "Israel", "spain": "Spain", "poland": "Poland", "sweden": "Sweden",
    "brazil": "Brazil", "mexico": "Mexico", "china": "China", "south korea": "South Korea",
    # Global boards (GitLab, Binance, Coinbase...) list roles in many more countries; knowing
    # them keeps "Remote, Turkey" out of an India/Australia search.
    "turkey": "Turkey", "türkiye": "Turkey", "turkiye": "Turkey", "korea": "South Korea",
    "republic of korea": "South Korea", "new zealand": "New Zealand", "hong kong": "Hong Kong",
    "taiwan": "Taiwan", "macau": "Macau", "philippines": "Philippines", "vietnam": "Vietnam",
    "viet nam": "Vietnam", "indonesia": "Indonesia", "malaysia": "Malaysia", "thailand": "Thailand",
    "bangladesh": "Bangladesh", "pakistan": "Pakistan", "sri lanka": "Sri Lanka", "nepal": "Nepal",
    "cambodia": "Cambodia", "saudi arabia": "Saudi Arabia", "ksa": "Saudi Arabia", "qatar": "Qatar",
    "bahrain": "Bahrain", "kuwait": "Kuwait", "oman": "Oman", "jordan": "Jordan", "lebanon": "Lebanon",
    "egypt": "Egypt", "morocco": "Morocco", "tunisia": "Tunisia", "nigeria": "Nigeria",
    "kenya": "Kenya", "ghana": "Ghana", "south africa": "South Africa", "ethiopia": "Ethiopia",
    "rwanda": "Rwanda", "uganda": "Uganda", "tanzania": "Tanzania", "italy": "Italy",
    "portugal": "Portugal", "belgium": "Belgium", "austria": "Austria", "denmark": "Denmark",
    "norway": "Norway", "finland": "Finland", "greece": "Greece", "romania": "Romania",
    "hungary": "Hungary", "czech republic": "Czech Republic", "czechia": "Czech Republic",
    "slovakia": "Slovakia", "slovenia": "Slovenia", "croatia": "Croatia", "serbia": "Serbia",
    "bulgaria": "Bulgaria", "ukraine": "Ukraine", "lithuania": "Lithuania", "latvia": "Latvia",
    "estonia": "Estonia", "luxembourg": "Luxembourg", "cyprus": "Cyprus", "malta": "Malta",
    "iceland": "Iceland", "russia": "Russia", "belarus": "Belarus", "armenia": "Armenia",
    "kazakhstan": "Kazakhstan", "azerbaijan": "Azerbaijan", "argentina": "Argentina",
    "chile": "Chile", "colombia": "Colombia", "peru": "Peru", "uruguay": "Uruguay",
    "costa rica": "Costa Rica", "ecuador": "Ecuador", "venezuela": "Venezuela",
    "guatemala": "Guatemala", "panama": "Panama", "puerto rico": "Puerto Rico",
    "scotland": "United Kingdom", "wales": "United Kingdom",
}  # fmt: skip
# Place names that contain a country alias but are somewhere else entirely.
_ALIAS_SHADOWS = re.compile(r"\bnew (?:mexico|south wales)\b")

_CITY_COUNTRY: dict[str, str] = {
    **dict.fromkeys((
        "bengaluru", "bangalore", "mumbai", "delhi", "new delhi", "gurugram", "gurgaon", "noida",
        "hyderabad", "pune", "chennai", "kolkata", "ahmedabad", "jaipur", "kochi", "chandigarh",
        "indore", "coimbatore", "trivandrum", "thiruvananthapuram", "mysuru", "mysore",
        "navi mumbai", "thane", "ghaziabad", "faridabad", "greater noida", "vadodara", "surat",
        "nagpur", "bhubaneswar", "visakhapatnam", "vizag", "lucknow", "mohali", "bhopal", "sanand",
        "madurai", "mangalore", "mangaluru", "guwahati", "kanpur", "vijayawada", "gandhinagar",
        # States and regions (as they appear in ATS location strings)
        "karnataka", "maharashtra", "telangana", "tamil nadu", "haryana", "uttar pradesh", "gujarat",
        "kerala", "west bengal", "andhra pradesh", "rajasthan", "punjab", "odisha", "madhya pradesh",
        "delhi ncr",
    ), "India"),
    **dict.fromkeys((
        "sydney", "melbourne", "brisbane", "perth", "adelaide", "canberra", "hobart", "gold coast",
        "darwin", "geelong", "wollongong", "parramatta", "north sydney", "macquarie park", "docklands",
        "sunshine coast", "newcastle, nsw", "newcastle, australia",
        "new south wales", "queensland", "western australia", "south australia", "tasmania",
        "australian capital territory", "northern territory", "victoria, australia",
    ), "Australia"),
    **dict.fromkeys((
        "new york", "san francisco", "seattle", "austin", "boston", "mountain view", "palo alto",
        "menlo park", "sunnyvale", "san jose", "los angeles", "chicago", "redmond", "cambridge, ma",
        "denver", "atlanta", "washington, dc", "pittsburgh", "san diego",
    ), "United States"),
    **dict.fromkeys(("london", "manchester", "edinburgh", "cambridge, uk", "oxford"), "United Kingdom"),
    **dict.fromkeys(("toronto", "vancouver", "montreal", "waterloo", "ottawa"), "Canada"),
    **dict.fromkeys(("berlin", "munich", "münchen", "hamburg", "frankfurt"), "Germany"),
    "amsterdam": "Netherlands", "paris": "France", "dublin": "Ireland", "zurich": "Switzerland",
    "tokyo": "Japan", "dubai": "United Arab Emirates",
    "tel aviv": "Israel", "singapore": "Singapore", "stockholm": "Sweden", "warsaw": "Poland",
    **dict.fromkeys((
        "alabama", "alaska", "arizona", "arkansas", "california", "colorado", "connecticut",
        "delaware", "florida", "hawaii", "idaho", "illinois", "indiana", "iowa", "kansas", "kentucky",
        "louisiana", "maryland", "massachusetts", "michigan", "minnesota", "mississippi", "missouri",
        "montana", "nebraska", "nevada", "new hampshire", "new jersey", "new mexico", "north carolina",
        "north dakota", "ohio", "oklahoma", "oregon", "pennsylvania", "rhode island", "south carolina",
        "south dakota", "tennessee", "texas", "utah", "vermont", "virginia", "wisconsin", "wyoming",
        "raleigh", "dallas", "houston", "miami", "phoenix", "portland", "philadelphia", "detroit",
        "minneapolis", "salt lake city", "nashville", "irvine", "santa clara", "san mateo",
        "bellevue", "kirkland", "boulder",
    ), "United States"),
    **dict.fromkeys(("glasgow", "leeds", "bristol, uk", "belfast", "reading, uk"), "United Kingdom"),
    **dict.fromkeys(("calgary", "edmonton", "winnipeg", "quebec", "ontario", "british columbia", "alberta"), "Canada"),
    **dict.fromkeys(("cologne", "köln", "stuttgart", "düsseldorf", "dusseldorf", "leipzig", "dresden"), "Germany"),
    **dict.fromkeys(("rotterdam", "utrecht", "eindhoven", "the hague"), "Netherlands"),
    **dict.fromkeys(("lyon", "toulouse", "grenoble"), "France"),
    **dict.fromkeys(("istanbul", "ankara", "izmir"), "Turkey"),
    **dict.fromkeys(("manila", "makati", "taguig", "cebu", "quezon city"), "Philippines"),
    **dict.fromkeys(("jakarta", "bandung", "surabaya"), "Indonesia"),
    **dict.fromkeys(("kuala lumpur", "penang", "cyberjaya"), "Malaysia"),
    **dict.fromkeys(("ho chi minh", "hanoi", "da nang"), "Vietnam"),
    **dict.fromkeys(("taipei", "hsinchu"), "Taiwan"),
    **dict.fromkeys(("seoul", "pangyo"), "South Korea"),
    **dict.fromkeys(("beijing", "shanghai", "shenzhen", "hangzhou", "guangzhou", "chengdu", "suzhou"), "China"),
    **dict.fromkeys(("osaka", "kyoto", "fukuoka"), "Japan"),
    **dict.fromkeys(("auckland", "wellington", "christchurch"), "New Zealand"),
    **dict.fromkeys(("sao paulo", "são paulo", "rio de janeiro", "florianopolis", "belo horizonte"), "Brazil"),
    **dict.fromkeys(("buenos aires",), "Argentina"),
    **dict.fromkeys(("bogota", "bogotá", "medellin", "medellín"), "Colombia"),
    **dict.fromkeys(("guadalajara", "monterrey"), "Mexico"),
    **dict.fromkeys(("madrid", "barcelona", "malaga", "málaga"), "Spain"),
    **dict.fromkeys(("milan", "milano", "rome", "turin"), "Italy"),
    **dict.fromkeys(("lisbon", "lisboa"), "Portugal"),
    **dict.fromkeys(("brussels", "antwerp"), "Belgium"),
    **dict.fromkeys(("vienna", "wien"), "Austria"),
    **dict.fromkeys(("copenhagen", "aarhus"), "Denmark"),
    "oslo": "Norway", "helsinki": "Finland", "espoo": "Finland", "athens, greece": "Greece",
    **dict.fromkeys(("prague", "brno"), "Czech Republic"),
    **dict.fromkeys(("bucharest", "cluj"), "Romania"),
    "budapest": "Hungary", "vilnius": "Lithuania", "riga": "Latvia", "tallinn": "Estonia",
    "belgrade": "Serbia", "zagreb": "Croatia",
    **dict.fromkeys(("kyiv", "kiev", "lviv", "kharkiv"), "Ukraine"),
    **dict.fromkeys(("krakow", "kraków", "wroclaw", "wrocław", "gdansk", "gdańsk", "poznan"), "Poland"),
    **dict.fromkeys(("cape town", "johannesburg", "durban"), "South Africa"),
    **dict.fromkeys(("lagos", "abuja"), "Nigeria"),
    "nairobi": "Kenya", "cairo": "Egypt", "casablanca": "Morocco", "accra": "Ghana",
    **dict.fromkeys(("riyadh", "jeddah"), "Saudi Arabia"),
    "doha": "Qatar", "abu dhabi": "United Arab Emirates", "manama": "Bahrain",
    **dict.fromkeys(("karachi", "lahore", "islamabad"), "Pakistan"),
    "dhaka": "Bangladesh", "colombo": "Sri Lanka", "kathmandu": "Nepal",
    **dict.fromkeys(("haifa", "herzliya"), "Israel"),
    "bangkok": "Thailand",
}  # fmt: skip

_US_STATE = re.compile(
    r",\s*(ca|ny|wa|tx|ma|il|co|ga|nc|va|pa|nj|or|fl|az|mn|ut|md|dc)\b", re.IGNORECASE
)


# Codes that ATS feeds (notably Workday) use as a whole location part: "IN, BANGALORE", "AU, Queensland".
_PART_CODES: dict[str, str] = {
    "in": "India", "ind": "India", "au": "Australia", "aus": "Australia",
    "nsw": "Australia", "qld": "Australia", "vic": "Australia",
    "sg": "Singapore", "sgp": "Singapore", "gb": "United Kingdom", "gbr": "United Kingdom",
    "de": "Germany", "deu": "Germany", "ca": "Canada", "jp": "Japan", "nl": "Netherlands",
    "ie": "Ireland", "fr": "France", "ae": "United Arab Emirates", "il": "Israel", "usa": "United States",
}  # fmt: skip
_US_STATE_CODES = {
    "in",
    "ca",
    "de",
    "il",
    "ia",
    "ma",
    "me",
    "md",
    "mn",
    "mo",
    "pa",
    "va",
    "wa",
    "co",
    "ct",
    "ga",
    "id",
}
_PART_SPLIT = re.compile(r"\s*[,;/|]\s*|\s+-\s+")


def extract_countries(locations: list[str]) -> list[str]:
    found: dict[str, None] = {}
    for location in locations:
        lowered = location.lower()
        parts = [part.strip().rstrip(".") for part in _PART_SPLIT.split(lowered) if part.strip()]
        if len(parts) > 1:
            # Workday-style leading country code: "IN, Bangalore", "AU, Queensland, Brisbane".
            if parts[0] in _PART_CODES:
                found.setdefault(_PART_CODES[parts[0]], None)
            # Trailing codes are ambiguous with US states ("Indianapolis, IN", "Mountain View, CA"),
            # so only codes that are not also state abbreviations count at the end.
            if parts[-1] in _PART_CODES and parts[-1] not in _US_STATE_CODES:
                found.setdefault(_PART_CODES[parts[-1]], None)
        if location.strip().upper() in {"IN", "AU", "IND", "AUS"}:
            found.setdefault(_PART_CODES[location.strip().lower()], None)
        unshadowed = _ALIAS_SHADOWS.sub(" ", lowered)
        for alias, country in _COUNTRY_ALIASES.items():
            if len(alias) <= 3:
                if re.search(rf"(^|[\s,(/-]){re.escape(alias)}($|[\s,)/-])", unshadowed):
                    found.setdefault(country, None)
            elif re.search(rf"\b{re.escape(alias)}\b", unshadowed):
                found.setdefault(country, None)
        for city, country in _CITY_COUNTRY.items():
            if re.search(rf"\b{re.escape(city)}\b", lowered):
                found.setdefault(country, None)
        if _US_STATE.search(location):
            found.setdefault("United States", None)
    return list(found)


# --- classification -----------------------------------------------------------------------------

_HINT_TYPES: dict[str, EmploymentType] = {
    "intern": EmploymentType.INTERNSHIP, "internship": EmploymentType.INTERNSHIP,
    "fulltime": EmploymentType.FULL_TIME, "full-time": EmploymentType.FULL_TIME,
    "full time": EmploymentType.FULL_TIME, "full_time": EmploymentType.FULL_TIME,
    "permanent": EmploymentType.FULL_TIME, "regular": EmploymentType.FULL_TIME,
    "parttime": EmploymentType.PART_TIME, "part-time": EmploymentType.PART_TIME,
    "part time": EmploymentType.PART_TIME, "part_time": EmploymentType.PART_TIME,
    "contract": EmploymentType.CONTRACT, "contractor": EmploymentType.CONTRACT,
    "freelance": EmploymentType.FREELANCE, "temporary": EmploymentType.TEMPORARY,
    "temp": EmploymentType.TEMPORARY, "apprenticeship": EmploymentType.APPRENTICESHIP,
}  # fmt: skip

_TITLE_TYPES: list[tuple[re.Pattern[str], EmploymentType]] = [
    (re.compile(r"\b(intern|interns|internship|co-?op|trainee|summer analyst|apprentice)\b", re.I),
     EmploymentType.INTERNSHIP),
    (re.compile(r"\bpart[- ]time\b", re.I), EmploymentType.PART_TIME),
    (re.compile(r"\b(contract|contractor|freelance)\b", re.I), EmploymentType.CONTRACT),
    (re.compile(r"\b(research (assistant|associate|fellow)|postdoc(toral)?|phd researcher)\b", re.I),
     EmploymentType.RESEARCH),
]  # fmt: skip


# Experienced titles: a description that mentions interns ("you'll mentor our interns") does not
# make the role an internship.
_EXPERIENCED_TITLE = re.compile(
    r"\b(senior|sr|staff|principal|lead|manager|director|head of|avp|vp|vice president|chief|architect)\b",
    re.I,
)
# Only wording that describes the role itself as an internship.
_INTERNSHIP_DESCRIPTION = re.compile(
    r"\b(?:this|our|an|the|paid|summer|winter|\d+[- ]months?)\s+internship\b"
    r"|\binternship\s+(?:program|programme|position|role|opportunity|period|duration)\b"
    r"|\b(?:as|for) an intern\b"
)


def detect_employment_type(title: str, hint: str | None, description: str) -> EmploymentType | None:
    for pattern, kind in _TITLE_TYPES:
        if pattern.search(title):
            return kind
    if hint:
        key = hint.strip().lower()
        for token, kind in _HINT_TYPES.items():
            # Whole words only: "intern" is not in "International".
            if re.search(rf"(?<![a-z]){re.escape(token)}(?![a-z])", key):
                return kind
    head = description[:800].lower()
    if not _EXPERIENCED_TITLE.search(title) and _INTERNSHIP_DESCRIPTION.search(head):
        return EmploymentType.INTERNSHIP
    if re.search(r"\bfull[- ]time\b", head):
        return EmploymentType.FULL_TIME
    if re.search(r"\bpart[- ]time\b", head):
        return EmploymentType.PART_TIME
    return None


def detect_remote(
    title: str, locations: list[str], description: str, hint: str | None = None
) -> RemoteType:
    joined = " ".join(locations).lower()
    if hint:
        h = hint.lower()
        if "hybrid" in h:
            return RemoteType.HYBRID
        if "remote" in h or "telecommute" in h:
            return RemoteType.REMOTE
        if "on-site" in h or "onsite" in h or "office" in h:
            return RemoteType.ONSITE
    if "hybrid" in joined or "hybrid" in title.lower():
        return RemoteType.HYBRID
    if "remote" in joined or re.search(r"\bremote\b", title, re.I):
        return RemoteType.REMOTE
    lowered = description.lower()
    if re.search(r"\bhybrid\b", lowered):
        return RemoteType.HYBRID
    if re.search(r"\b(fully remote|100% remote|remote[- ]first|work from anywhere)\b", lowered):
        return RemoteType.REMOTE
    if re.search(r"\b(on-?site|in[- ]office|in person)\b", lowered):
        return RemoteType.ONSITE
    return RemoteType.UNKNOWN


# Numbered levels only count right after a role noun: "SDE I", "Software Engineer 2", "Analyst III".
_LEVEL_NOUN = (
    r"\b(?:engineer|developer|scientist|analyst|sde|swe|sdet|associate|specialist|consultant"
    r"|designer|researcher|programmer|technologist)"
)


def detect_seniority(title: str, employment_type: EmploymentType | None) -> SeniorityLevel:
    t = title.lower()
    # Whole words: "Internal Audit Manager" and "International Sales Lead" are not internships.
    if re.search(r"\b(interns?|internships?)\b", t):
        return SeniorityLevel.INTERN
    if re.search(r"\b(associate product manager|apm)\b", t) and not re.search(
        r"\b(senior|sr|lead|principal|group)\b", t
    ):
        return SeniorityLevel.ENTRY  # APM is a new-graduate role
    if re.search(r"\b(head of|director|vp|vice president|chief|manager)\b", t):
        return SeniorityLevel.MANAGER
    if re.search(r"\b(staff|principal|lead|distinguished|architect)\b", t):
        return SeniorityLevel.LEAD
    # Banks title mid-career roles "AVP" (assistant vice president).
    if re.search(r"\b(senior|sr|avp)\b|\b(iii|iv)\b", t) or re.search(
        rf"{_LEVEL_NOUN}\s*[345]\b", t
    ):
        return SeniorityLevel.SENIOR
    # The title names no level, so a posting marked as an internship is one. A level in the title
    # wins over that mark ("Senior Software Engineer" is never an internship).
    if employment_type == EmploymentType.INTERNSHIP:
        return SeniorityLevel.INTERN
    if (
        re.search(
            r"\b(junior|jr|entry[- ]level|new grad|graduate|fresher|trainee|early[- ]career"
            r"|campus hire|apprentice)\b",
            t,
        )
        or re.match(r"^associate\b(?!.*\b(director|principal)\b)", t)
        or re.search(rf"{_LEVEL_NOUN}\s*(?:i|1)\b", t)
    ):
        return SeniorityLevel.ENTRY
    if re.search(r"\b(ii|mid[- ]level)\b", t) or re.search(rf"{_LEVEL_NOUN}\s*2\b", t):
        return SeniorityLevel.MID
    return SeniorityLevel.UNKNOWN


# --- canonical job ------------------------------------------------------------------------------


@dataclass
class NormalizedJob:
    external_id: str | None
    company: str
    title: str
    normalized_title: str
    location: str | None
    locations: list[str]
    normalized_location: str
    countries: list[str]
    employment_type: EmploymentType | None
    remote_type: RemoteType
    seniority: SeniorityLevel
    department: str | None
    description: str
    description_hash: str
    posted_at: datetime | None
    deadline: datetime | None
    salary_min: float | None
    salary_max: float | None
    currency: str | None
    salary_period: CompensationPeriod | None
    canonical_url: str | None
    application_url: str | None
    application_platform: ApplicationPlatform
    dedup_key: str
    raw_metadata: dict[str, Any] = field(default_factory=dict)


def normalize(raw: RawJob) -> NormalizedJob:
    description = clean_text(
        html_to_text(raw.description_html) if raw.description_html else (raw.description_text or "")
    )
    locations = [
        " ".join(loc.split()) for loc in (raw.locations or ([raw.location] if raw.location else []))
    ]
    locations = [loc for loc in dict.fromkeys(locations) if loc]
    location = raw.location or ("; ".join(locations) if locations else None)
    employment_type = detect_employment_type(raw.title, raw.employment_type_hint, description)
    listing_url = canonicalize_url(raw.url) or canonicalize_url(raw.apply_url)
    apply_url = raw.apply_url or raw.url
    company = " ".join(raw.company.split())[:200]
    title = " ".join(raw.title.split())[:300]
    normalized_location = normalize_location(location or "")
    salary = raw.salary
    return NormalizedJob(
        external_id=(raw.external_id or None) and str(raw.external_id)[:200],
        company=company,
        title=title,
        normalized_title=normalize_title(title),
        location=location[:300] if location else None,
        locations=locations[:20],
        normalized_location=normalized_location,
        countries=extract_countries(locations),
        employment_type=employment_type,
        remote_type=detect_remote(title, locations, description, raw.remote_hint),
        seniority=detect_seniority(title, employment_type),
        department=raw.department[:200] if raw.department else None,
        description=description,
        description_hash=description_hash(f"{title}\n{description}"),
        posted_at=ensure_aware(raw.posted_at) if raw.posted_at else None,
        deadline=ensure_aware(raw.deadline) if raw.deadline else None,
        salary_min=salary.minimum if salary else None,
        salary_max=salary.maximum if salary else None,
        currency=(salary.currency or "").upper()[:3] or None if salary else None,
        salary_period=salary.period if salary else None,
        canonical_url=listing_url,
        application_url=apply_url[:1000] if apply_url else None,
        application_platform=detect_platform(apply_url),
        dedup_key=f"{normalize_company(company)}|{normalize_title(title)}|{normalized_location}"[
            :700
        ],
        raw_metadata=raw.metadata,
    )
