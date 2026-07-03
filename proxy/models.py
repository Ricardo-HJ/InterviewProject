from __future__ import annotations

import hashlib
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, Field

ProviderName = Literal["atlas", "beacon", "cobalt"]

# Canonical employment status. UNKNOWN is a safety net for shapes we can't map.
EmploymentStatus = Literal["ACTIVE", "ON_LEAVE", "TERMINATED", "UNKNOWN"]

# Field names that participate in merge/conflict detection, in display order.
MERGED_FIELDS: tuple[str, ...] = (
    "name",
    "title",
    "department",
    "salary_annual",
    "hire_date",
    "status",
)


class SourceRef(BaseModel):
    """One provider's contribution to a single field."""

    provider: ProviderName
    provider_id: str  # native id, e.g. "A-1001", "5001", "cobalt-9f3a2b"
    raw: Any  # the value BEFORE normalization (drives the provenance popover)
    normalized: Any = None  # this provider's own value AFTER normalization. Equals the
    # field value for a single-provider record; after a merge it lets us compare each
    # provider's contribution (e.g. salary-disagreement checks) without re-parsing raw.


class FieldValue(BaseModel):
    """A normalized, chosen value plus every provider source that fed into it."""

    value: Any
    sources: list[SourceRef] = Field(default_factory=list)


class Employee(BaseModel):
    """Canonical, deduplicated person.

    After normalization (one provider) this holds a single source per field.
    After aggregation (cross-provider merge) fields may carry several sources and
    ``conflicts`` lists the fields whose providers disagreed.
    """

    canonical_id: str  # stable hash of the normalized email
    email: str  # dedup key, normalized (trimmed + lowercased)

    name: FieldValue
    title: FieldValue
    department: FieldValue
    salary_annual: FieldValue  # value is a Decimal (annual)
    currency: str | None
    hire_date: FieldValue  # value is ISO "YYYY-MM-DD"
    status: FieldValue  # value is an EmploymentStatus

    providers: list[ProviderName] = Field(default_factory=list)
    provider_ids: dict[str, str] = Field(default_factory=dict)
    conflicts: list[str] = Field(default_factory=list)


def canonical_id(email: str) -> str:
    """Stable, short id derived from the normalized email."""
    return hashlib.sha256(email.encode("utf-8")).hexdigest()[:16]


def single_source_field(
    value: Any, provider: ProviderName, provider_id: str, raw: Any
) -> FieldValue:
    """Build a field that has exactly one source — used by the normalizers."""
    return FieldValue(
        value=value,
        sources=[
            SourceRef(
                provider=provider,
                provider_id=provider_id,
                raw=raw,
                normalized=value,
            )
        ],
    )


def build_single_provider_employee(
    *,
    provider: ProviderName,
    provider_id: str,
    email: str,
    name: tuple[Any, Any],  # (normalized_value, raw_value)
    title: tuple[Any, Any],
    department: tuple[Any, Any],
    salary_annual: tuple[Decimal | None, Any],
    currency: str | None,
    hire_date: tuple[str | None, Any],
    status: tuple[EmploymentStatus, Any],
) -> Employee:
    """Assemble a single-provider ``Employee`` from (normalized, raw) field pairs.

    Keeping this in one place means the three normalizers only worry about *how* to
    derive each value, not how to wire provenance.
    """

    def fld(pair: tuple[Any, Any]) -> FieldValue:
        norm, raw = pair
        return single_source_field(norm, provider, provider_id, raw)

    return Employee(
        canonical_id=canonical_id(email),
        email=email,
        name=fld(name),
        title=fld(title),
        department=fld(department),
        salary_annual=fld(salary_annual),
        currency=currency,
        hire_date=fld(hire_date),
        status=fld(status),
        providers=[provider],
        provider_ids={provider: provider_id},
    )
