from __future__ import annotations

import json
import logging
from typing import Any

import config
from issues import Issue
from models import Employee

from .client import ai_available, ask_json

logger = logging.getLogger("proxy.ai")

_SYSTEM = (
    "You are an HR data assistant. You are given a detected data-quality issue for an "
    "employee and the per-provider evidence behind it. Explain the SINGLE most likely "
    "root cause in ONE short plain-English sentence. Be specific but brief — no preamble, "
    "no restating the issue. Use ONLY the evidence provided — do NOT invent update times "
    "or recency; you may refer to provider precedence. Respond with a JSON object of the "
    "form {\"root_cause\": \"...\"} and nothing else."
)

_SCHEMA = {
    "type": "object",
    "properties": {"root_cause": {"type": "string"}},
    "required": ["root_cause"],
    "additionalProperties": False,
}


def build_rootcause_context(issue: Issue, emp: Employee) -> dict[str, Any]:
    """Compact view of an issue + the field's per-provider values for the prompt.

    Pure — unit-testable without AI.
    """
    field_sources: dict[str, Any] = {}
    if issue.field and hasattr(emp, issue.field):
        fv = getattr(emp, issue.field)
        field_sources = {
            s.provider: {"raw": s.raw, "normalized": s.normalized} for s in fv.sources
        }
    return {
        "kind": issue.kind,
        "field": issue.field,
        "deterministic_summary": issue.summary,
        "evidence": issue.evidence,
        "providers": list(emp.providers),
        "field_by_provider": field_sources,
    }


async def explain_issue(issue: Issue, emp: Employee) -> str | None:
    """Return a likely-cause explanation, or ``None`` if AI is off/failed."""
    if not ai_available():
        return None

    prompt = "Explain the likely root cause of this issue:\n" + json.dumps(
        build_rootcause_context(issue, emp), ensure_ascii=False, default=str
    )
    data = await ask_json(
        prompt,
        schema=_SCHEMA,
        system=_SYSTEM,
        model=config.AI_MODEL_REASON,
        max_tokens=200,
    )
    if not isinstance(data, dict):
        return None
    cause = data.get("root_cause")
    return cause if isinstance(cause, str) and cause.strip() else None
