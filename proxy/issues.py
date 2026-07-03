"""Deterministic data-quality / anomaly detection.

Everything here is **pure and deterministic**: given the merged employees it returns
a list of ``Issue`` objects, each with a plain-English ``summary`` that stands on its
own. No LLM is involved — detecting and describing an anomaly is templating, not
judgment, so the deterministic ``summary`` is the final output the UI shows.

Detectors
---------
- ``status_conflict``     — providers disagree on employment status (Yuki is the real hit).
- ``salary_outlier``      — salary is ≥ ``SALARY_Z_THRESHOLD`` σ from the mean of the
  person's **peer group** (same role + org unit), not the whole company.
- ``salary_disagreement`` — providers report a *materially* different salary for one
  person. Sub-currency gaps from unit conversion (Beacon's monthly×12 rounding leaves
  ~0.04 differences) are deliberately ignored so we don't raise hundreds of false alarms.
- ``missing_data``        — a critical field is absent.
- ``impossible_date``     — hire date is unparseable, in the future, or absurdly old.

Why "peers" = role × org unit (not the whole company): salary legitimately varies by
role and department — engineers out-earn HR generalists by design — so a company-wide
z-score just re-flags every well-paid role. We compare each person only against others
in the same normalized (org unit, role) group, and skip groups smaller than
``MIN_PEERS`` rather than judge from too little data. On the seed data this correctly
surfaces *no* salary outliers: once role/org-unit is accounted for, the apparent ones
were an artifact of comparing engineers against recruiters.
"""

from __future__ import annotations

import re
import statistics
from collections import defaultdict
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Literal

from pydantic import BaseModel, Field

from models import Employee

IssueKind = Literal[
    "status_conflict",
    "salary_outlier",
    "salary_disagreement",
    "missing_data",
    "impossible_date",
]
Severity = Literal["high", "medium", "low"]

# --- tunables (documented + defensible; overridable in tests) ----------------
SALARY_Z_THRESHOLD = 2.5  # σ from the PEER-GROUP mean before a salary is an outlier
MIN_PEERS = 12  # don't judge a salary against fewer peers than this (skip instead)
SALARY_REL_TOLERANCE = 0.005  # 0.5% — cross-provider gaps below BOTH this and the
SALARY_ABS_TOLERANCE = Decimal("1")  # absolute floor count as rounding, not conflict
EARLIEST_PLAUSIBLE_HIRE = date(1950, 1, 1)

# Fields whose absence is worth flagging, with how loudly.
CRITICAL_FIELDS: tuple[str, ...] = (
    "name",
    "title",
    "department",
    "salary_annual",
    "hire_date",
)
_HIGH_VALUE_FIELDS = {"salary_annual", "hire_date"}


class Issue(BaseModel):
    """One data-quality finding, attachable to an employee and to the ``/issues`` feed."""

    id: str  # stable: "<canonical_id>:<kind>[:<field>]"
    canonical_id: str
    employee_name: str
    employee_email: str
    kind: IssueKind
    field: str | None = None
    severity: Severity
    summary: str  # deterministic plain-English description — the final output
    evidence: dict[str, Any] = Field(default_factory=dict)
    is_new: bool = False  # first time this id has been observed by any client


def _issue_id(canonical_id: str, kind: str, field: str | None = None) -> str:
    return f"{canonical_id}:{kind}" + (f":{field}" if field else "")


def _name(emp: Employee) -> str:
    return emp.name.value or emp.email


def _new(emp: Employee, kind: IssueKind, severity: Severity, summary: str,
         *, field: str | None = None, evidence: dict | None = None) -> Issue:
    return Issue(
        id=_issue_id(emp.canonical_id, kind, field),
        canonical_id=emp.canonical_id,
        employee_name=_name(emp),
        employee_email=emp.email,
        kind=kind,
        field=field,
        severity=severity,
        summary=summary,
        evidence=evidence or {},
    )


# --- peer grouping for salary outliers ---------------------------------------
# Department and title are both canonicalized at normalization
# (transform.canonical_department / canonical_title), so peers group cleanly across
# providers without any suffix/abbreviation folding here.
PeerStats = tuple[float, float, int]  # (mean, stdev, n)


def _peer_key(emp: Employee) -> tuple[str, str]:
    """(org unit, title) a salary should be compared within."""
    dept = (emp.department.value or "").strip().lower()
    title = re.sub(r"\s+", " ", (emp.title.value or "").strip().lower())
    return dept, title


def _stats(values: list[float]) -> PeerStats | None:
    """Mean/stdev/n, or None if there are too few peers (or no spread) to judge."""
    if len(values) < MIN_PEERS:
        return None
    sd = statistics.pstdev(values)
    if sd <= 0:
        return None
    return statistics.fmean(values), sd, len(values)


def _peer_stats(
    employees: list[Employee],
) -> tuple[dict[tuple[str, str], PeerStats | None], dict[str, PeerStats | None]]:
    """Pre-compute salary stats per (org unit, role) and per role (the fallback)."""
    by_peer: dict[tuple[str, str], list[float]] = defaultdict(list)
    by_role: dict[str, list[float]] = defaultdict(list)
    for emp in employees:
        value = emp.salary_annual.value
        if value is None:
            continue
        dept, role = _peer_key(emp)
        by_peer[(dept, role)].append(float(value))
        by_role[role].append(float(value))
    return (
        {key: _stats(vals) for key, vals in by_peer.items()},
        {key: _stats(vals) for key, vals in by_role.items()},
    )


# --- individual detectors ----------------------------------------------------
def _status_conflict(emp: Employee) -> list[Issue]:
    if "status" not in emp.conflicts:
        return []
    by_provider = {s.provider: s.normalized for s in emp.status.sources}
    pretty = ", ".join(f"{p}={v}" for p, v in by_provider.items())
    summary = (
        f"Providers disagree on employment status ({pretty}); "
        f"canonical resolves to {emp.status.value} by provider precedence — verify which is current."
    )
    return [
        _new(
            emp, "status_conflict", "high", summary, field="status",
            evidence={
                "by_provider": by_provider,
                "canonical": emp.status.value,
                "raw": {s.provider: s.raw for s in emp.status.sources},
            },
        )
    ]


def _salary_outlier(
    emp: Employee,
    peer_stats: dict[tuple[str, str], PeerStats | None],
    role_stats: dict[str, PeerStats | None],
) -> list[Issue]:
    value = emp.salary_annual.value
    if value is None:
        return []
    dept, role = _peer_key(emp)
    # Prefer (org unit, role); fall back to role-only; skip if too few peers either way.
    stats = peer_stats.get((dept, role)) or role_stats.get(role)
    if stats is None:
        return []
    mean, std, n = stats
    z = (float(value) - mean) / std
    if abs(z) < SALARY_Z_THRESHOLD:
        return []
    direction = "above" if z > 0 else "below"
    scope = emp.title.value or role
    where = f" in {emp.department.value}" if emp.department.value else ""
    cur = emp.currency or ""
    summary = (
        f"Salary {float(value):,.0f} {cur}".rstrip()
        + f" is {abs(z):.1f}σ {direction} the {n} peers in the same role"
        + f" ({scope}{where}; peer mean {mean:,.0f}) — worth verifying."
    )
    return [
        _new(
            emp, "salary_outlier", "medium", summary, field="salary_annual",
            evidence={
                "salary": float(value),
                "peer_mean": round(mean, 2),
                "peer_std": round(std, 2),
                "z": round(z, 2),
                "direction": direction,
                "peer_count": n,
                "peer_role": role,
                "peer_dept": dept,
                "currency": emp.currency,
            },
        )
    ]


def _salary_disagreement(emp: Employee) -> list[Issue]:
    sources = [s for s in emp.salary_annual.sources if s.normalized is not None]
    if len(sources) < 2:
        return []
    try:
        by_provider = {s.provider: Decimal(str(s.normalized)) for s in sources}
    except (InvalidOperation, ValueError):
        return []
    values = list(by_provider.values())
    spread = max(values) - min(values)
    median = sorted(values)[len(values) // 2]
    rel = float(spread / median) if median else 0.0
    # Below BOTH tolerances → unit-conversion rounding, not a real disagreement.
    if spread <= SALARY_ABS_TOLERANCE and rel <= SALARY_REL_TOLERANCE:
        return []
    pretty = ", ".join(f"{p}={float(v):,.0f}" for p, v in by_provider.items())
    summary = (
        f"Providers report different salaries ({pretty}); "
        f"spread {float(spread):,.0f} ({rel * 100:.1f}%) exceeds rounding tolerance."
    )
    return [
        _new(
            emp, "salary_disagreement", "high", summary, field="salary_annual",
            evidence={
                "by_provider": {p: float(v) for p, v in by_provider.items()},
                "spread": float(spread),
                "relative": round(rel, 4),
                "canonical": float(emp.salary_annual.value)
                if emp.salary_annual.value is not None
                else None,
            },
        )
    ]


def _missing_data(emp: Employee) -> list[Issue]:
    out: list[Issue] = []
    for field in CRITICAL_FIELDS:
        if getattr(emp, field).value in (None, ""):
            severity: Severity = "medium" if field in _HIGH_VALUE_FIELDS else "low"
            label = field.replace("_", " ")
            out.append(
                _new(
                    emp, "missing_data", severity,
                    f"Missing {label} — no provider supplied a value.",
                    field=field, evidence={"providers": emp.providers},
                )
            )
    return out


def _impossible_date(emp: Employee, today: date) -> list[Issue]:
    value = emp.hire_date.value
    if value in (None, ""):
        return []  # absence is handled by _missing_data
    try:
        parsed = date.fromisoformat(str(value))
    except ValueError:
        return [
            _new(
                emp, "impossible_date", "high",
                f"Hire date {value!r} is not a valid date.",
                field="hire_date", evidence={"value": value},
            )
        ]
    if parsed > today:
        return [
            _new(
                emp, "impossible_date", "high",
                f"Hire date {value} is in the future.",
                field="hire_date",
                evidence={"value": value, "today": today.isoformat()},
            )
        ]
    if parsed < EARLIEST_PLAUSIBLE_HIRE:
        return [
            _new(
                emp, "impossible_date", "medium",
                f"Hire date {value} is implausibly old.",
                field="hire_date", evidence={"value": value},
            )
        ]
    return []


# --- orchestration -----------------------------------------------------------
_SEVERITY_RANK = {"high": 0, "medium": 1, "low": 2}


def detect_issues(employees: list[Employee], *, today: date | None = None) -> list[Issue]:
    """Run every deterministic detector over the merged employees.

    Pure: same input → same output, no I/O, no AI. Results are sorted high→low
    severity (then name, then kind) so the feed and any UI are stable.
    """
    today = today or date.today()
    peer_stats, role_stats = _peer_stats(employees)

    issues: list[Issue] = []
    for emp in employees:
        issues += _status_conflict(emp)
        issues += _salary_disagreement(emp)
        issues += _salary_outlier(emp, peer_stats, role_stats)
        issues += _missing_data(emp)
        issues += _impossible_date(emp, today)

    issues.sort(key=lambda i: (_SEVERITY_RANK[i.severity], i.employee_name, i.kind))
    return issues
