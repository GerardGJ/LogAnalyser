import re
from typing import Literal

Route = Literal["sql", "diagnostic", "unsupported"]

# Deterministic keyword/phrase rules, per the POC decision in TODO.md 2.4 to
# prefer this over an LLM router for now. Phrases are wrapped in \b...\b so
# e.g. "fail" doesn't match inside "failover".
_SQL_PHRASES = [
    r"how many", r"count", r"list", r"average", r"avg", r"sum", r"total",
    r"top\s+\d+", r"group\s+by", r"which\s+(?:app|service|source_file)",
    r"show\s+(?:events|logs|records)", r"select", r"where", r"filter",
    r"most", r"least", r"by\s+app", r"by\s+level", r"source_file",
]
_DIAGNOSTIC_PHRASES = [
    r"why", r"root\s+cause", r"crash(?:ed)?", r"fail(?:ed|ure)?",
    r"broke(?:n)?", r"exception", r"traceback", r"diagnos(?:e|is)", r"debug",
]

_SQL_REGEX = re.compile("|".join(rf"\b{p}\b" for p in _SQL_PHRASES), re.IGNORECASE)
_DIAGNOSTIC_REGEX = re.compile("|".join(rf"\b{p}\b" for p in _DIAGNOSTIC_PHRASES), re.IGNORECASE)


def route_query(question: str) -> Route:
    """
    Classifies a natural-language question into a downstream agent route.

    Deterministic and keyword-based: matches diagnostic phrases (root-cause
    intent, e.g. "why", "crash", "traceback") ahead of SQL phrases (metrics/
    lookup intent, e.g. "how many", "top 5", "group by") so a mixed-intent
    question like "why are there so many errors, show me the top apps"
    routes to the more specific diagnostic ask rather than the SQL one.
    Falls back to "unsupported" when neither matches or the input is empty.
    """
    if not question or not question.strip():
        return "unsupported"

    if _DIAGNOSTIC_REGEX.search(question):
        return "diagnostic"
    if _SQL_REGEX.search(question):
        return "sql"
    return "unsupported"
