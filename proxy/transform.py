from __future__ import annotations

import re
from datetime import datetime, timezone
from decimal import Decimal

from models import EmploymentStatus

_CENTS = Decimal(100)
_MONTHS = Decimal(12)
_MONEY = Decimal("0.01")


def clean_email(value: str | None) -> str:
    """Canonical email: trim stray whitespace (Cobalt) and lowercase (Beacon)."""
    return (value or "").strip().lower()


#Removes redundant provider-specific org-unit suffixes from department names, such as "dept", "team", "studio", or "ops".
_DEPT_SUFFIX = re.compile(r"\s+(?:dept|team|studio|ops)\.?$", re.I)

def canonical_department(value: str | None) -> str | None:
    """Drop a redundant provider-specific org-unit suffix; bare names pass through."""
    if value is None:
        return None
    cleaned = value.strip()
    return _DEPT_SUFFIX.sub("", cleaned) or cleaned


#Change each abreviation to its canonical form, e.g. "Sr." -> "Senior", "Eng" -> "Engineer".
_TITLE_ABBREV: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\bsr\b\.?", re.I), "Senior"),
    (re.compile(r"\bjr\b\.?", re.I), "Junior"),
    (re.compile(r"\beng\b\.?", re.I), "Engineer"),
)


def canonical_title(value: str | None) -> str | None:
    """Expand seniority abbreviations ("Sr." -> "Senior") and tidy whitespace."""
    if value is None:
        return None
    text = value.strip()
    for pattern, repl in _TITLE_ABBREV:
        text = pattern.sub(repl, text)
    return re.sub(r"\s+", " ", text).strip() or value.strip()


def to_annual_from_cents(cents: int) -> Decimal:
    """Atlas: integer annual cents -> annual major units."""
    return (Decimal(cents) / _CENTS).quantize(_MONEY)


def to_annual_from_monthly(monthly: str | float | int) -> Decimal:
    """Beacon: decimal monthly amount -> annual."""
    return (Decimal(str(monthly)) * _MONTHS).quantize(_MONEY)


def to_annual_from_year(value: int | float | str) -> Decimal:
    """Cobalt: already annual (pay.unit == 'year')."""
    return Decimal(str(value)).quantize(_MONEY)


def iso_from_iso(value: str) -> str:
    """Atlas hire_date is already ISO; validate and normalize to YYYY-MM-DD."""
    return datetime.strptime(value, "%Y-%m-%d").date().isoformat()


def iso_from_unix_ms(ms: int) -> str:
    """Beacon started_at is unix milliseconds (UTC)."""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).date().isoformat()


def iso_from_ddmmyyyy(value: str) -> str:
    """Cobalt joined is DD/MM/YYYY."""
    return datetime.strptime(value.strip(), "%d/%m/%Y").date().isoformat()


def atlas_status(value: str) -> EmploymentStatus:
    """Atlas employment_status is an UPPERCASE enum; pass through known values."""
    mapping: dict[str, EmploymentStatus] = {
        "ACTIVE": "ACTIVE",
        "ON_LEAVE": "ON_LEAVE",
        "TERMINATED": "TERMINATED",
    }
    return mapping.get((value or "").upper(), "UNKNOWN")


def beacon_status(is_active: bool, on_leave: bool) -> EmploymentStatus:
    """Beacon splits status across two booleans. On-leave takes precedence over
    active (an on-leave employee is still active=True in the source)."""
    if on_leave:
        return "ON_LEAVE"
    if not is_active:
        return "TERMINATED"
    return "ACTIVE"


def cobalt_status(value: str) -> EmploymentStatus:
    """Cobalt lifecycle_status is a lowercase string."""
    mapping: dict[str, EmploymentStatus] = {
        "employed": "ACTIVE",
        "on_leave": "ON_LEAVE",
        "former": "TERMINATED",
    }
    return mapping.get((value or "").strip().lower(), "UNKNOWN")
