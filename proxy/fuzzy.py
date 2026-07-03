"""Probabilistic (fuzzy) dedup.

Exact-key dedup (``aggregate.py``) merges people who share ``(email, hire_date)``.
Whoever is left as a single-provider record might still be the same human as another
single — a typo'd email, a surname spelling variant, a record in another provider. This
module scores likely same-person pairs and returns ranked merge candidates with a
confidence + per-signal breakdown. Suggestion-only: a human confirms before any merge.

Approach (deterministic, no AI):
- **Blocking** keeps it cheap: group singles by ``(first-3, last-3)`` name-prefix so we
  only compare plausibly-similar records (tolerant of suffix typos like Ruiz/Ruis), never
  the full O(n²).
- **Score 0..1**: a weighted blend of string similarity (name, email, title, department)
  and hire-date proximity. Hire date carries the most weight because a shared *name* is a
  weak signal on its own — this dataset has 15 different "Liang Wilson"s.

Suggestion-only and fully deterministic: the ranked score is the confidence a reviewer
sees, and a human confirms before any merge.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from difflib import SequenceMatcher
from itertools import combinations
from typing import Any

from pydantic import BaseModel, Field

from models import Employee

# --- tunables (documented + defensible) --------------------------------------
MIN_SCORE = 0.80  # below this a pair isn't worth a reviewer's attention
MAX_CANDIDATES = 50  # cap the feed (ranked by score)
WEIGHTS: dict[str, float] = {
    "name": 0.25,
    "email": 0.15,
    "title": 0.15,
    "department": 0.15,
    "hire_date": 0.30,
}
BULK_MATCH_THRESHOLD = 0.95  # a signal at/above this counts as "not a meaningful difference"


class PersonRef(BaseModel):
    """Compact view of one side of a candidate pair (drives the side-by-side card)."""

    canonical_id: str
    name: Any
    email: str
    title: Any
    department: Any
    hire_date: Any
    providers: list[str] = Field(default_factory=list)


class MergeCandidate(BaseModel):
    id: str  # stable: "<left.canonical_id>|<right.canonical_id>"
    left: PersonRef
    right: PersonRef
    score: float  # deterministic confidence 0..1
    signals: dict[str, float]  # per-field similarity breakdown
    is_new: bool = False  # first time this id has been observed by any client


class MergeBulkFilter(BaseModel):
    """A bulk-triage criterion compiled from free text ("approve any match >= 90%",
    "approve any merge where the difference is in the title and/or email")."""

    min_score: float | None = None
    differs_only_in: list[str] | None = None  # signal keys allowed to be < threshold;
    # every OTHER signal must be >= BULK_MATCH_THRESHOLD


def matches_bulk_filter(c: MergeCandidate, f: MergeBulkFilter) -> bool:
    if f.min_score is not None and c.score < f.min_score:
        return False
    if f.differs_only_in is not None:
        allowed = set(f.differs_only_in)
        for key, value in c.signals.items():
            if key not in allowed and value < BULK_MATCH_THRESHOLD:
                return False
    return True


def _ratio(a: Any, b: Any) -> float:
    return SequenceMatcher(None, str(a or ""), str(b or "")).ratio()


def _hire_proximity(a: Any, b: Any) -> float:
    """1.0 same day, 0.7 within ~6 weeks, 0.3 within ~13 months, else 0."""
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    try:
        gap = abs((date.fromisoformat(str(a)) - date.fromisoformat(str(b))).days)
    except ValueError:
        return 0.0
    if gap <= 45:
        return 0.7
    if gap <= 400:
        return 0.3
    return 0.0


def _signals(a: Employee, b: Employee) -> dict[str, float]:
    return {
        "name": _ratio(a.name.value, b.name.value),
        "email": _ratio(a.email, b.email),
        "title": _ratio(a.title.value, b.title.value),
        "department": _ratio(a.department.value, b.department.value),
        "hire_date": _hire_proximity(a.hire_date.value, b.hire_date.value),
    }


def _score(signals: dict[str, float]) -> float:
    return round(sum(WEIGHTS[k] * v for k, v in signals.items()), 4)


def _block_key(emp: Employee) -> tuple[str, str] | None:
    parts = (emp.name.value or "").strip().lower().split()
    if len(parts) < 2:
        return None
    return (parts[0][:3], parts[-1][:3])


def _ref(emp: Employee) -> PersonRef:
    return PersonRef(
        canonical_id=emp.canonical_id,
        name=emp.name.value,
        email=emp.email,
        title=emp.title.value,
        department=emp.department.value,
        hire_date=emp.hire_date.value,
        providers=list(emp.providers),
    )


def find_merge_candidates(
    employees: list[Employee],
    *,
    min_score: float = MIN_SCORE,
    max_candidates: int = MAX_CANDIDATES,
) -> list[MergeCandidate]:
    """Ranked same-person candidates among the single-provider ("unmatched") records."""
    singles = [e for e in employees if len(e.providers) == 1]

    blocks: dict[tuple[str, str], list[Employee]] = defaultdict(list)
    for emp in singles:
        key = _block_key(emp)
        if key:
            blocks[key].append(emp)

    candidates: list[MergeCandidate] = []
    for group in blocks.values():
        if len(group) < 2:
            continue
        for a, b in combinations(group, 2):
            signals = _signals(a, b)
            score = _score(signals)
            if score >= min_score:
                left, right = _ref(a), _ref(b)
                candidates.append(
                    MergeCandidate(
                        id=f"{left.canonical_id}|{right.canonical_id}",
                        left=left,
                        right=right,
                        score=score,
                        signals={k: round(v, 3) for k, v in signals.items()},
                    )
                )

    candidates.sort(key=lambda c: c.score, reverse=True)
    return candidates[:max_candidates]
