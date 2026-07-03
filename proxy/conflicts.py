"""Cross-provider conflict resolution — deterministic.

When providers disagree on a text field (name, title), the merge in ``aggregate.py``
keeps a canonical value by provider precedence and records the field in ``conflicts``.
This module suggests the best canonical value using small, documented rules — no LLM,
because each of these is a rule we can state plainly:

- ``name``:  prefer the spelling with diacritics (the accented form is the correct one).
- ``title``: prefer the most specific (longest) form, keeping seniority information.

Suggestions are advisory — the canonical value is never overwritten automatically.
``department`` is canonicalized at normalization (``transform.canonical_department``), so
any residual department disagreement is a genuine difference with no string rule to pick
between — excluded here, like status. Status disagreements are a data-quality flag
(``issues.py``); salary/date gaps are rounding or data errors — all excluded here.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from models import Employee

RESOLVABLE_FIELDS: tuple[str, ...] = ("name", "title")


class CandidateValue(BaseModel):
    provider: str
    value: Any


class ConflictSuggestion(BaseModel):
    id: str  # stable: "<canonical_id>:<field>"
    canonical_id: str
    employee_name: str
    employee_email: str
    field: str
    candidates: list[CandidateValue] = Field(default_factory=list)
    current: Any  # precedence-chosen canonical value (what /employees shows today)
    suggested: Any  # rule-chosen recommendation — always one of ``candidates``
    reason: str  # which rule produced the suggestion
    is_new: bool = False  # first time this id has been observed by any client


class ConflictBulkFilter(BaseModel):
    """A bulk-triage criterion compiled from free text ("approve all changes that
    recommend senior in title") — unbounded phrasing is exactly the case this project
    reserves AI for; the filter itself is applied deterministically below."""

    field: str | None = None  # "name" | "title" | "department"
    keyword: str | None = None  # case-insensitive substring match on `suggested`


def matches_bulk_filter(s: ConflictSuggestion, f: ConflictBulkFilter) -> bool:
    if f.field and s.field != f.field:
        return False
    if f.keyword and f.keyword.lower() not in str(s.suggested).lower():
        return False
    return True


def _diacritic_count(value: str) -> int:
    return sum(1 for ch in (value or "") if ord(ch) > 127 and ch.isalpha())


def _resolve(field: str, values: list[str]) -> tuple[Any, str]:
    """Pick the best canonical value among the distinct candidates, plus a reason."""
    if field == "name":
        best = max(values, key=lambda v: (_diacritic_count(v), len(v)))
        if _diacritic_count(best) > 0:
            return best, "Prefer the spelling with diacritics (more accurate)."
        return best, "Prefer the most complete spelling."
    # title (default): most specific = longest, so seniority information is kept.
    return max(values, key=len), "Prefer the most specific (longest) title."


def _distinct_candidates(emp: Employee, field: str) -> list[CandidateValue]:
    """Per-provider values for a field, de-duplicated by normalized value."""
    seen: set = set()
    out: list[CandidateValue] = []
    for src in getattr(emp, field).sources:
        value = src.normalized
        if value in (None, "") or value in seen:
            continue
        seen.add(value)
        out.append(CandidateValue(provider=src.provider, value=value))
    return out


def gather_conflicts(employees: list[Employee]) -> list[ConflictSuggestion]:
    """One suggestion per (employee, conflicting resolvable field), resolved by rule.

    Returns an empty list for people whose only disagreement is status, salary, or
    hire date (those aren't string-canonicalization choices).
    """
    out: list[ConflictSuggestion] = []
    for emp in employees:
        for field in RESOLVABLE_FIELDS:
            if field not in emp.conflicts:
                continue
            candidates = _distinct_candidates(emp, field)
            if len(candidates) < 2:
                continue
            suggested, reason = _resolve(field, [c.value for c in candidates])
            out.append(
                ConflictSuggestion(
                    id=f"{emp.canonical_id}:{field}",
                    canonical_id=emp.canonical_id,
                    employee_name=emp.name.value or emp.email,
                    employee_email=emp.email,
                    field=field,
                    candidates=candidates,
                    current=getattr(emp, field).value,
                    suggested=suggested,
                    reason=reason,
                )
            )
    return out
