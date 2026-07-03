from __future__ import annotations

from collections import OrderedDict

from models import (
    MERGED_FIELDS,
    Employee,
    FieldValue,
    ProviderName,
    SourceRef,
    canonical_id,
)
from titles import LEVELS, normalize_title

# Lower index == higher priority when choosing the canonical value.
PROVIDER_PRECEDENCE: tuple[ProviderName, ...] = ("atlas", "beacon", "cobalt")


def _dedup_key(emp: Employee) -> tuple[str, str]:
    return (emp.email, emp.hire_date.value or "")


def _precedence_rank(provider: str) -> int:
    try:
        return PROVIDER_PRECEDENCE.index(provider)  # type: ignore[arg-type]
    except ValueError:
        return len(PROVIDER_PRECEDENCE)


def _merge_field(field_name: str, group: list[Employee]) -> tuple[FieldValue, bool]:
    """Merge one field across a group; return (merged field, conflict?).

    - sources: every provider's contribution, ordered by precedence
    - value: first non-null value by provider precedence
    - conflict: more than one distinct non-null normalized value across providers
    """
    members = sorted(group, key=lambda e: _precedence_rank(e.providers[0]))

    sources: list[SourceRef] = []
    chosen = None
    distinct_values = []
    for emp in members:
        field: FieldValue = getattr(emp, field_name)
        sources.extend(field.sources)
        if field.value not in (None, ""):
            if chosen is None:
                chosen = field.value
            if field.value not in distinct_values:
                distinct_values.append(field.value)

    return FieldValue(value=chosen, sources=sources), len(distinct_values) > 1


def _merge_title(group: list[Employee]) -> tuple[FieldValue, bool]:
    """Title is resolved deterministically, not by bare precedence: keep the most senior
    form ("Software Engineer" + "Senior Software Engineer" -> "Senior Software Engineer").

    A title disagreement is only a *conflict* when the seniority-stripped role genuinely
    differs across providers — a pure seniority difference is resolved here and never
    surfaced for review.
    """
    members = sorted(group, key=lambda e: _precedence_rank(e.providers[0]))

    sources: list[SourceRef] = []
    candidates: list[tuple[int, int, str]] = []  # (seniority rank, length, value)
    roles: list[str] = []
    for emp in members:
        field: FieldValue = emp.title
        sources.extend(field.sources)
        if field.value in (None, ""):
            continue
        norm = normalize_title(field.value)
        level_rank = LEVELS.index(norm.level) if norm.level in LEVELS else -1
        candidates.append((level_rank, len(field.value), field.value))
        if norm.role not in roles:
            roles.append(norm.role)

    if not candidates:
        return FieldValue(value=None, sources=sources), False
    # Most senior wins; tie -> most specific (longest); final tie -> provider precedence
    # (candidates are in precedence order, and max keeps the first of equal maxima).
    chosen = max(candidates, key=lambda c: (c[0], c[1]))[2]
    return FieldValue(value=chosen, sources=sources), len(roles) > 1


def _merge_currency(group: list[Employee]) -> str | None:
    members = sorted(group, key=lambda e: _precedence_rank(e.providers[0]))
    for emp in members:
        if emp.currency:
            return emp.currency
    return None


def merge_group(group: list[Employee]) -> Employee:
    """Collapse all single-provider records for one person into a canonical Employee."""
    members = sorted(group, key=lambda e: _precedence_rank(e.providers[0]))
    email = members[0].email

    fields: dict[str, FieldValue] = {}
    conflicts: list[str] = []
    for field_name in MERGED_FIELDS:
        if field_name == "title":
            merged, is_conflict = _merge_title(members)
        else:
            merged, is_conflict = _merge_field(field_name, members)
        fields[field_name] = merged
        if is_conflict:
            conflicts.append(field_name)

    providers: list[ProviderName] = [emp.providers[0] for emp in members]
    provider_ids: dict[str, str] = {emp.providers[0]: emp.provider_ids[emp.providers[0]] for emp in members}

    return Employee(
        canonical_id=canonical_id(email),
        email=email,
        name=fields["name"],
        title=fields["title"],
        department=fields["department"],
        salary_annual=fields["salary_annual"],
        currency=_merge_currency(members),
        hire_date=fields["hire_date"],
        status=fields["status"],
        providers=providers,
        provider_ids=provider_ids,
        conflicts=conflicts,
    )


def aggregate(records: list[Employee]) -> list[Employee]:
    """Group single-provider records by identity and merge each group.

    Insertion order is preserved so output is stable across runs (handy for the UI
    and for tests).
    """
    groups: "OrderedDict[tuple[str, str], list[Employee]]" = OrderedDict()
    for rec in records:
        groups.setdefault(_dedup_key(rec), []).append(rec)
    return [merge_group(group) for group in groups.values()]
