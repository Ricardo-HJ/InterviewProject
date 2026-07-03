from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from models import Employee


class QueryFilter(BaseModel):
    department: str | None = None  # case-insensitive substring on canonical department
    role: str | None = None  # case-insensitive substring on title
    status: str | None = None  # ACTIVE / ON_LEAVE / TERMINATED
    hired_after: str | None = None  # ISO date, inclusive lower bound
    hired_before: str | None = None  # ISO date, inclusive upper bound
    provider_count: int | None = None  # exact (1 == "only in one provider")
    providers: list[str] | None = None  # must appear in all of these providers
    salary_min: float | None = None
    salary_max: float | None = None
    limit: int | None = None


def _iso(value) -> str | None:
    try:
        return date.fromisoformat(str(value)).isoformat()
    except (ValueError, TypeError):
        return None


def apply_filter(employees: list[Employee], f: QueryFilter) -> list[Employee]:
    """Return the employees matching every set field of the filter (ANDed)."""
    out: list[Employee] = []
    for e in employees:
        if f.department and f.department.lower() not in (e.department.value or "").lower():
            continue
        if f.role and f.role.lower() not in (e.title.value or "").lower():
            continue
        if f.status and (e.status.value or "") != f.status:
            continue

        hire = _iso(e.hire_date.value)
        if f.hired_after and (hire is None or hire < f.hired_after):
            continue
        if f.hired_before and (hire is None or hire > f.hired_before):
            continue

        if f.provider_count is not None and len(e.providers) != f.provider_count:
            continue
        if f.providers and not all(p in e.providers for p in f.providers):
            continue

        salary = float(e.salary_annual.value) if e.salary_annual.value is not None else None
        if f.salary_min is not None and (salary is None or salary < f.salary_min):
            continue
        if f.salary_max is not None and (salary is None or salary > f.salary_max):
            continue

        out.append(e)

    if f.limit and f.limit > 0:
        out = out[: f.limit]
    return out
