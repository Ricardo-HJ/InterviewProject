from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel

from models import Employee

# Controlled vocabularies the taxonomy maps onto.
FAMILIES: tuple[str, ...] = (
    "Engineering",
    "Data",
    "Design",
    "Product",
    "Sales",
    "Marketing",
    "People",
    "Customer Success",
    "Operations",
    "Other",
)
LEVELS: tuple[str, ...] = (
    "Junior",
    "Mid",
    "Senior",
    "Staff",
    "Lead",
    "Manager",
    "Director",
)


class CanonicalTitle(BaseModel):
    role: str  # seniority-stripped canonical role, e.g. "Software Engineer"
    family: str  # one of FAMILIES
    level: str  # one of LEVELS
    source: Literal["ai", "fallback"] = "fallback"


_SENIORITY_PREFIX = re.compile(r"^(senior|sr\.?|junior|jr\.?|lead|staff|principal)\s+", re.I)


def _strip_role(raw: str) -> str:
    stripped = _SENIORITY_PREFIX.sub("", (raw or "").strip()).strip()
    return stripped or (raw or "").strip()


def _fallback_level(raw: str) -> str:
    """Conservative: read level only from clear seniority words, never from a role noun
    like 'Manager' ('Account Manager' is an IC role, not a management level)."""
    s = (raw or "").lower()
    if re.match(r"^(staff|principal)\b", s):
        return "Staff"
    if re.match(r"^lead\b", s) or s.endswith(" lead"):
        return "Lead"
    if re.match(r"^(senior|sr\.?)\b", s):
        return "Senior"
    if re.match(r"^(junior|jr\.?|associate|intern)\b", s):
        return "Junior"
    return "Mid"


def _fallback_family(raw: str) -> str:
    s = (raw or "").lower()
    if "engineer" in s or "devops" in s:
        return "Engineering"
    if "data" in s or "analytics" in s or "scientist" in s:
        return "Data"
    if "design" in s or "ux" in s:
        return "Design"
    if "product" in s:
        return "Product"
    if "sales" in s or "account" in s:
        return "Sales"
    if "marketing" in s or "content" in s or "growth" in s:
        return "Marketing"
    if "recruit" in s or "people" in s or " hr" in f" {s}" or "talent" in s:
        return "People"
    if "customer" in s or "success" in s or "support" in s or "implementation" in s:
        return "Customer Success"
    return "Other"


def normalize_title(raw: str) -> CanonicalTitle:
    """Deterministic baseline normalization — always available, never raises."""
    return CanonicalTitle(
        role=_strip_role(raw),
        family=_fallback_family(raw),
        level=_fallback_level(raw),
        source="fallback",
    )


def unique_titles(employees: list[Employee]) -> list[str]:
    """Distinct non-empty raw titles, in first-seen order (stable)."""
    seen: dict[str, None] = {}
    for emp in employees:
        title = emp.title.value
        if title and title not in seen:
            seen[title] = None
    return list(seen)
