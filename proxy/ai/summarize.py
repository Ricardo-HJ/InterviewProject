from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any

import config
from models import Employee

from .client import ai_available, ask_json

logger = logging.getLogger("proxy.ai")

_FIELDS = ("name", "title", "department", "salary_annual", "hire_date", "status")

_SYSTEM = (
    "You are an HR data assistant. You are given one employee's record as it appears "
    "across multiple HR systems ('providers'). Write a very short plain-English summary "
    "— ONE or at most TWO sentences — capturing only the key takeaway: whether the "
    "providers broadly agree, and the single most important discrepancy if there is one. "
    "Do NOT enumerate every field or restate values that already agree. Use ONLY the "
    "evidence provided — do NOT invent update times or recency. Respond with a JSON "
    "object of the form {\"summary\": \"...\"} and nothing else."
)

_SCHEMA = {
    "type": "object",
    "properties": {"summary": {"type": "string"}},
    "required": ["summary"],
    "additionalProperties": False,
}


def _jsonable(value: Any) -> Any:
    """Make provenance values JSON-serializable (Decimal salaries → str)."""
    if isinstance(value, Decimal):
        return str(value)
    return value


def build_summary_context(emp: Employee) -> dict[str, Any]:
    """Compact, provider-attributed view of one employee for the summary prompt.

    Pure — no AI, no I/O — so it's unit-testable on its own.
    """
    fields: dict[str, Any] = {}
    for key in _FIELDS:
        fv = getattr(emp, key)
        fields[key] = {
            "canonical": _jsonable(fv.value),
            "by_provider": {
                s.provider: {
                    "raw": _jsonable(s.raw),
                    "normalized": _jsonable(s.normalized),
                }
                for s in fv.sources
            },
        }
    return {
        "email": emp.email,
        "providers": list(emp.providers),
        "conflicting_fields": list(emp.conflicts),
        "currency": emp.currency,
        "fields": fields,
    }


async def summarize_employee(emp: Employee) -> str | None:
    """Return a short cross-provider narrative, or ``None`` if AI is off/failed."""
    if not ai_available():
        return None

    prompt = "Summarize this employee's data across providers:\n" + json.dumps(
        build_summary_context(emp), ensure_ascii=False
    )
    data = await ask_json(
        prompt,
        schema=_SCHEMA,
        system=_SYSTEM,
        model=config.AI_MODEL_REASON,
        max_tokens=256,
    )
    if not isinstance(data, dict):
        return None
    summary = data.get("summary")
    return summary if isinstance(summary, str) and summary.strip() else None
