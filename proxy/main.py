from __future__ import annotations

import asyncio
import time
from collections import Counter
from contextlib import asynccontextmanager
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

import config
import demo_schema_drift
import demo_seed
from aggregate import aggregate
from ai import (
    ai_available,
    apply_mapping,
    compile_conflict_filter,
    compile_merge_filter,
    compile_query,
    explain_issue,
    infer_mapping,
    refine_titles,
    simulate_merge,
    summarize_employee,
)
from conflicts import gather_conflicts, matches_bulk_filter as matches_conflict_filter
from fuzzy import find_merge_candidates, matches_bulk_filter as matches_merge_filter
from issues import detect_issues
from models import Employee
from providers import PROVIDERS
from query import apply_filter
from titles import normalize_title, unique_titles


@dataclass
class ProviderStatus:
    """Per-provider outcome, surfaced so the UI can show a partial banner."""

    provider: str
    ok: bool
    count: int = 0  # raw records fetched
    error: str | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # One shared HTTP client for the app's lifetime (connection pooling).
    async with httpx.AsyncClient() as client:
        app.state.http = client
        app.state.cache = None  # (timestamp, payload)
        # Ids of every issue/suggestion/merge-candidate ever observed, so the Inbox can
        # flag genuinely new items (``is_new``) instead of silently blending them in.
        # In-memory only — resets on restart, same as the employees cache above.
        app.state.seen_ids = set()
        # Per-process memo of LLM-inferred schema mappings (self-healing), one
        # per provider — so we infer a drifted provider's map once, not per record.
        app.state.schema_mappings = {}
        yield


app = FastAPI(title="Employee Aggregator Proxy", lifespan=lifespan)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# Provider modules keyed by NAME, so the self-healing demos can look one up by name.
_PROVIDER_BY_NAME = {module.NAME: module for module in PROVIDERS}

# Per-process memo of mappings inferred for the DEMO drifted shapes — deliberately
# separate from the live ``app.state.schema_mappings`` so the demo stays fully isolated
# from the production heal path (and we don't re-infer on every request).
_DEMO_SCHEMA_MEMO: dict = {}


async def _heal_record(provider_name: str, raw: dict) -> dict:
    """Run one drifted record through the self-healing fallback and return the evidence.

    Shared by ``/schema-mapping/demo`` (one record) and ``/self-heal/recovered`` (many):
    show the deterministic normalizer failing, the LLM-inferred mapping, and the
    recovered canonical Employee. Reuses ``infer_mapping`` / ``apply_mapping`` from the
    real heal path; ``recovered_employee`` is ``null`` when the AI layer is unavailable.
    """
    module = _PROVIDER_BY_NAME[provider_name]

    try:
        module.normalize(raw)
        deterministic_error = None  # (won't happen — the payload is deliberately drifted)
    except Exception as exc:  # noqa: BLE001 — capturing the failure IS the demo
        deterministic_error = f"{type(exc).__name__}: {exc}"

    mapping = _DEMO_SCHEMA_MEMO.get(provider_name)
    if mapping is None:
        mapping = await infer_mapping(provider_name, [raw])
        if mapping is not None:
            _DEMO_SCHEMA_MEMO[provider_name] = mapping
    recovered = apply_mapping(mapping, raw, provider=provider_name) if mapping is not None else None

    return {
        "provider": provider_name,
        "drifted_raw": raw,
        "deterministic_error": deterministic_error,
        "inferred_mapping": mapping.model_dump(mode="json") if mapping else None,
        "recovered_employee": recovered.model_dump(mode="json") if recovered else None,
    }


@app.get("/schema-mapping/demo")
async def schema_mapping_demo() -> dict:
    """Self-healing schema mapping demo — single Beacon payload.

    Walks the fallback end-to-end on one built-in "drifted" Beacon payload: the
    deterministic normalizer fails, the LLM infers a field map, and applying it yields
    a valid canonical Employee. Advisory: payloads are ``null`` (with a ``note``) when
    the AI layer is unavailable.
    """
    provider, raw = demo_schema_drift.DRIFTED_SAMPLES[0]  # the Beacon shape
    record = await _heal_record(provider, raw)
    return {
        "ai": ai_available(),
        **record,
        "note": None if record["inferred_mapping"] else _ai_feature_note("Schema inference"),
    }


@app.get("/self-heal/recovered")
async def self_heal_recovered() -> dict:
    """Employees recovered by self-healing from forced-drift payloads.

    Each built-in drifted record breaks its provider's hand-written normalizer; the LLM
    infers the new field map and we recover a canonical Employee, returned with the
    evidence (drifted raw + deterministic error + inferred mapping). Isolated from the
    live pipeline — the static mocks never drift, so this forces it for the demo.
    """
    records = [await _heal_record(name, raw) for name, raw in demo_schema_drift.DRIFTED_SAMPLES]
    any_recovered = any(r["recovered_employee"] for r in records)
    return {
        "ai": ai_available(),
        "records": records,
        "note": None if any_recovered else _ai_feature_note("Self-healing"),
    }


async def _collect_provider(
    module, client: httpx.AsyncClient
) -> tuple[list[Employee], ProviderStatus]:
    """Fetch + normalize one provider. Never raises — failures become a status row so
    one provider being down can't 500 the whole response.

    Records the hand-written normalizer can't parse are, by default, skipped. When
    self-healing is enabled (and AI is available) we instead try to recover them via an
    LLM-inferred schema mapping — see ``_heal_failed`` and ``ai/schema_infer.py``.
    """
    name = module.NAME
    try:
        raw = await module.fetch(client)
    except Exception as exc:  # noqa: BLE001 — deliberately isolate provider failures
        return [], ProviderStatus(provider=name, ok=False, error=_describe(exc))

    normalized: list[Employee] = []
    failed: list[dict] = []
    for record in raw:
        try:
            normalized.append(module.normalize(record))
        except Exception:  # noqa: BLE001 — keep the rest; maybe self-heal below
            failed.append(record)

    if failed and config.SELF_HEAL_SCHEMA and ai_available():
        await _heal_failed(name, failed, normalized)

    return normalized, ProviderStatus(provider=name, ok=True, count=len(raw))


async def _heal_failed(name: str, failed: list[dict], out: list[Employee]) -> None:
    """Recover records a normalizer rejected by applying an LLM-inferred mapping.

    The mapping is inferred once per provider (memoized on ``app.state``) from a sample
    of the failed records, then applied deterministically and appended to ``out``. Any
    records that still don't apply cleanly are left skipped, as before.
    """
    memo = app.state.schema_mappings
    mapping = memo.get(name)
    if mapping is None:
        mapping = await infer_mapping(name, failed)
        if mapping is None:
            return
        memo[name] = mapping

    for record in failed:
        try:
            out.append(apply_mapping(mapping, record, provider=name))
        except Exception:  # noqa: BLE001 — a record the inferred map still can't parse
            continue


def _describe(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code} from {exc.request.url}"
    if isinstance(exc, httpx.RequestError):
        return f"{type(exc).__name__}: could not reach {exc.request.url}"
    return f"{type(exc).__name__}: {exc}"


async def _gather_employees(
    client: httpx.AsyncClient,
) -> tuple[list[Employee], list[ProviderStatus]]:
    """Fetch + normalize + merge across all providers (no caching, no AI)."""
    results = await asyncio.gather(
        *(_collect_provider(module, client) for module in PROVIDERS)
    )

    all_records: list[Employee] = []
    statuses: list[ProviderStatus] = []
    for records, status in results:
        all_records.extend(records)
        statuses.append(status)

    employees = aggregate(all_records)
    # Inject the perturbed near-duplicate(s) so the fuzzy-dedup demo has a real catch.
    if config.FUZZY_DEMO_SEED:
        employees.extend(demo_seed.demo_records())
    return employees, statuses


def _mark_new(items: list) -> None:
    """Flip ``is_new`` for ids not yet recorded in ``app.state.seen_ids``, then record
    every id as seen — so the *next* observer (any client) no longer sees it as new."""
    for item in items:
        item.is_new = item.id not in app.state.seen_ids
    app.state.seen_ids.update(item.id for item in items)


async def _employees_cached(
    refresh: bool,
) -> tuple[list[Employee], list[ProviderStatus]]:
    """Shared TTL cache of the merged employees so ``/employees`` and ``/issues``
    don't each re-hit the upstreams; ``?refresh=true`` forces a fresh fetch."""
    cache = app.state.cache
    now = time.monotonic()
    if not refresh and cache is not None and now - cache[0] < config.CACHE_TTL_SECONDS:
        return cache[1], cache[2]

    employees, statuses = await _gather_employees(app.state.http)
    app.state.cache = (now, employees, statuses)
    return employees, statuses


def _provider_summary(statuses: list[ProviderStatus]) -> dict:
    return {
        "partial": any(not s.ok for s in statuses),
        "providers": [s.__dict__ for s in statuses],
    }


def _uninterpretable_note() -> str:
    return (
        "This needs the AI layer (set ANTHROPIC_API_KEY)."
        if not ai_available()
        else "Could not interpret the query."
    )


def _ai_feature_note(label: str) -> str:
    """Note shown when an advisory AI feature produced no result — distinguishes
    'no key configured' from 'the call failed' so the UI can say which."""
    return (
        f"{label} needs the AI layer (set ANTHROPIC_API_KEY)."
        if not ai_available()
        else f"{label} is temporarily unavailable — the AI call returned no result."
    )


@app.get("/employees")
async def list_employees(refresh: bool = False) -> dict:
    """Unified, deduplicated employee list.

    Each employee carries any deterministic data-quality ``issues`` (status conflicts,
    salary outliers, etc.) so the table can badge rows without a second request. The
    plain-English AI explanations live on the richer ``/issues`` feed.
    """
    employees, statuses = await _employees_cached(refresh)

    issues_by_id: dict[str, list[dict]] = {}
    for issue in detect_issues(employees):
        issues_by_id.setdefault(issue.canonical_id, []).append(
            issue.model_dump(mode="json")
        )

    # Deterministic title normalization travels with every row (the AI-refined taxonomy
    # is at /titles). Always present, so the field never depends on the AI layer.
    payload = [
        {
            **e.model_dump(mode="json"),
            "issues": issues_by_id.get(e.canonical_id, []),
            "title_normalized": normalize_title(e.title.value).model_dump(mode="json"),
        }
        for e in employees
    ]
    return {"employees": payload, "count": len(employees), **_provider_summary(statuses)}


@app.get("/employees/{canonical_id}/summary")
async def employee_summary(canonical_id: str, refresh: bool = False) -> dict:
    """AI "What Happened to This Employee?" — a short cross-provider
    narrative. Advisory: ``summary`` is ``null`` (with a ``note``) when the AI layer
    is unavailable; the deterministic provenance view always stands on its own.
    """
    employees, _ = await _employees_cached(refresh)
    emp = next((e for e in employees if e.canonical_id == canonical_id), None)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    summary = await summarize_employee(emp)
    return {
        "ai": ai_available(),
        "summary": summary,
        "note": None if summary is not None else _ai_feature_note("This summary"),
    }


@app.get("/issues")
async def list_issues(refresh: bool = False) -> dict:
    """Data-quality / anomaly feed.

    Fully deterministic — each issue's ``summary`` is the final, human-readable
    description (no LLM: detecting/describing an anomaly is templating, not judgment).
    """
    employees, statuses = await _employees_cached(refresh)
    issues = detect_issues(employees)
    _mark_new(issues)

    by_kind: dict[str, int] = {}
    for issue in issues:
        by_kind[issue.kind] = by_kind.get(issue.kind, 0) + 1

    return {
        "issues": [i.model_dump(mode="json") for i in issues],
        "count": len(issues),
        "by_kind": by_kind,
        **_provider_summary(statuses),
    }


@app.get("/issues/root-cause")
async def issue_root_cause(id: str, refresh: bool = False) -> dict:
    """AI Root-Cause Analysis — the likely cause behind one detected
    issue (``id`` is the issue's stable id, which contains colons, so it's a query
    param). Advisory: ``root_cause`` is ``null`` (with a ``note``) when AI is off.
    """
    employees, _ = await _employees_cached(refresh)
    issues = detect_issues(employees)
    issue = next((i for i in issues if i.id == id), None)
    if issue is None:
        raise HTTPException(status_code=404, detail="Issue not found")
    emp = next((e for e in employees if e.canonical_id == issue.canonical_id), None)
    if emp is None:
        raise HTTPException(status_code=404, detail="Employee not found")

    root_cause = await explain_issue(issue, emp)
    return {
        "ai": ai_available(),
        "root_cause": root_cause,
        "note": None if root_cause is not None else _ai_feature_note("Root-cause analysis"),
    }


@app.get("/conflicts")
async def list_conflicts(refresh: bool = False) -> dict:
    """Conflict-resolution suggestions — deterministic.

    For each text field where providers disagree (name/title), recommend the best
    canonical value + the rule behind it (name→diacritics, title→most specific). Advisory
    only — the canonical value is never overwritten. (Department is canonicalized at
    normalization, so it has no residual string-resolution rule here.)
    """
    employees, statuses = await _employees_cached(refresh)
    suggestions = gather_conflicts(employees)
    _mark_new(suggestions)

    by_field: dict[str, int] = {}
    for s in suggestions:
        by_field[s.field] = by_field.get(s.field, 0) + 1
    changed = sum(1 for s in suggestions if s.suggested != s.current)

    return {
        "conflicts": [s.model_dump(mode="json") for s in suggestions],
        "count": len(suggestions),
        "by_field": by_field,
        "changed_from_default": changed,
        **_provider_summary(statuses),
    }


@app.get("/conflicts/bulk-filter")
async def conflicts_bulk_filter(q: str, refresh: bool = False) -> dict:
    """Bulk-triage criterion → filter (e.g. "approve all changes that recommend senior
    in title"). The LLM only ever emits a validated filter; matching against the current
    suggestions is deterministic. Returns identifying keys only — the frontend already
    holds the full suggestion objects from ``/conflicts``.
    """
    employees, _ = await _employees_cached(refresh)
    bulk_filter = await compile_conflict_filter(q)

    if bulk_filter is None:
        return {"query": q, "ai": ai_available(), "applied_filter": None,
                "note": _uninterpretable_note(), "matched": [], "count": 0}

    suggestions = gather_conflicts(employees)
    matched = [
        {"canonical_id": s.canonical_id, "field": s.field}
        for s in suggestions
        if matches_conflict_filter(s, bulk_filter)
    ]
    return {
        "query": q,
        "ai": True,
        "applied_filter": bulk_filter.model_dump(exclude_none=True),
        "matched": matched,
        "count": len(matched),
    }


@app.get("/merge-candidates")
async def list_merge_candidates(refresh: bool = False) -> dict:
    """Probabilistic (fuzzy) merge candidates — deterministic.

    Among the single-provider records that exact dedup left unmatched, rank likely
    same-person pairs by a similarity score with a per-signal breakdown. Suggestion-only
    — a human confirms before anything is merged.
    """
    employees, statuses = await _employees_cached(refresh)
    candidates = find_merge_candidates(employees)
    _mark_new(candidates)

    return {
        "merge_candidates": [c.model_dump(mode="json") for c in candidates],
        "count": len(candidates),
        **_provider_summary(statuses),
    }


@app.get("/merge-candidates/simulate")
async def merge_candidate_simulate(id: str, refresh: bool = False) -> dict:
    """AI Merge Simulator — predicted effects + risks of merging one
    candidate pair (``id`` is "<left>|<right>", so it's a query param). Advisory:
    ``simulation`` is ``null`` (with a ``note``) when AI is off; the deterministic
    similarity breakdown on the candidate card stands on its own.
    """
    employees, _ = await _employees_cached(refresh)
    candidate = next((c for c in find_merge_candidates(employees) if c.id == id), None)
    if candidate is None:
        raise HTTPException(status_code=404, detail="Merge candidate not found")

    simulation = await simulate_merge(candidate)
    return {
        "ai": ai_available(),
        "simulation": simulation.model_dump(mode="json") if simulation else None,
        "note": None if simulation is not None else _ai_feature_note("Merge simulation"),
    }


@app.get("/merge-candidates/bulk-filter")
async def merge_candidates_bulk_filter(q: str, refresh: bool = False) -> dict:
    """Bulk-triage criterion → filter (e.g. "approve any match >= 90%", "approve any
    merge where the difference is in the title and/or email"). Same pattern as
    ``/conflicts/bulk-filter``: the LLM emits a validated filter, matching is
    deterministic, and only identifying keys are returned.
    """
    employees, _ = await _employees_cached(refresh)
    bulk_filter = await compile_merge_filter(q)

    if bulk_filter is None:
        return {"query": q, "ai": ai_available(), "applied_filter": None,
                "note": _uninterpretable_note(), "matched": [], "count": 0}

    candidates = find_merge_candidates(employees)
    matched = [
        {"left_id": c.left.canonical_id, "right_id": c.right.canonical_id}
        for c in candidates
        if matches_merge_filter(c, bulk_filter)
    ]
    return {
        "query": q,
        "ai": True,
        "applied_filter": bulk_filter.model_dump(exclude_none=True),
        "matched": matched,
        "count": len(matched),
    }


@app.get("/titles")
async def list_titles(refresh: bool = False) -> dict:
    """Title taxonomy: each distinct raw title → canonical {role, family, level}.

    Deterministic baseline for every title (always present), with the LLM refining the
    ambiguous cases (e.g. IC 'Account Manager' vs a managerial title). ``source`` says
    which produced each mapping.
    """
    employees, statuses = await _employees_cached(refresh)
    raw_titles = unique_titles(employees)

    mapping = {title: normalize_title(title) for title in raw_titles}
    mapping.update(await refine_titles(raw_titles))  # AI overrides where it succeeded

    counts = Counter(e.title.value for e in employees if e.title.value)
    titles = [
        {"raw": title, "count": counts.get(title, 0), **canonical.model_dump(mode="json")}
        for title, canonical in mapping.items()
    ]
    titles.sort(key=lambda t: (-t["count"], t["raw"]))

    return {
        "titles": titles,
        "count": len(titles),
        "ai_refined": sum(1 for t in titles if t["source"] == "ai"),
        "ai": ai_available(),
        **_provider_summary(statuses),
    }


@app.get("/search")
async def search(q: str, refresh: bool = False) -> dict:
    """Natural-language search: a sentence → structured filter → results.

    The LLM compiles the query into a constrained filter (returned as ``applied_filter``
    for transparency); it's applied deterministically. Needs the AI layer — with no key
    the response says so rather than guessing.
    """
    employees, statuses = await _employees_cached(refresh)
    query_filter = await compile_query(q)

    if query_filter is None:
        note = (
            "Natural-language search needs the AI layer (set ANTHROPIC_API_KEY)."
            if not ai_available()
            else "Could not interpret the query."
        )
        return {"query": q, "ai": ai_available(), "applied_filter": None, "note": note,
                "employees": [], "count": 0}

    matched = apply_filter(employees, query_filter)
    return {
        "query": q,
        "ai": True,
        "applied_filter": query_filter.model_dump(exclude_none=True),
        "employees": [e.model_dump(mode="json") for e in matched],
        "count": len(matched),
        **_provider_summary(statuses),
    }
