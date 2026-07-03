from __future__ import annotations

import logging

import config
from conflicts import ConflictBulkFilter
from fuzzy import MergeBulkFilter

from .client import ai_available, ask_json

logger = logging.getLogger("proxy.ai")

_CONFLICT_SYSTEM = (
    "You translate a user's bulk-approval criterion into a JSON filter over "
    "conflict-resolution suggestions. Return a JSON object containing ONLY the fields "
    "the request clearly implies; omit all others. Allowed fields and types:\n"
    '- field: one of "name", "title" — which field the suggestion is for\n'
    "- keyword (string): a case-insensitive substring that must appear in the suggested "
    'value (e.g. "recommend senior in title" -> field "title", keyword "senior")\n'
    "Return JSON only, no prose."
)

_MERGE_SYSTEM = (
    "You translate a user's bulk-approval criterion into a JSON filter over "
    "probabilistic merge candidates. Each candidate has a confidence `score` (0..1) and "
    "per-field similarity `signals` for: name, email, title, department, hire_date. "
    "Return a JSON object containing ONLY the fields the request clearly implies; omit "
    "all others. Allowed fields and types:\n"
    '- min_score (number 0..1): "approve any match >= 90%" -> 0.9\n'
    "- differs_only_in (array of signal keys): the ONLY fields allowed to differ — every "
    'other field must be a near-exact match. "the difference is in the title and/or '
    'email" -> ["title", "email"]\n'
    "Return JSON only, no prose."
)


async def compile_conflict_filter(text: str) -> ConflictBulkFilter | None:
    """Compile a bulk-approval criterion into a ``ConflictBulkFilter``."""
    if not text or not text.strip() or not ai_available():
        return None

    data = await ask_json(
        f"Build a filter for this bulk-approval request:\n{text.strip()}",
        system=_CONFLICT_SYSTEM,
        model=config.AI_MODEL_FAST,
        max_tokens=256,
    )
    if not isinstance(data, dict):
        return None
    try:
        fields = {k: v for k, v in data.items() if k in ConflictBulkFilter.model_fields}
        return ConflictBulkFilter(**fields)
    except Exception as exc:  # noqa: BLE001 — bad shape degrades to "uninterpretable"
        logger.warning("Conflict bulk-filter compile failed: %s", exc)
        return None


async def compile_merge_filter(text: str) -> MergeBulkFilter | None:
    """Compile a bulk-approval criterion into a ``MergeBulkFilter``."""
    if not text or not text.strip() or not ai_available():
        return None

    data = await ask_json(
        f"Build a filter for this bulk-approval request:\n{text.strip()}",
        system=_MERGE_SYSTEM,
        model=config.AI_MODEL_FAST,
        max_tokens=256,
    )
    if not isinstance(data, dict):
        return None
    try:
        fields = {k: v for k, v in data.items() if k in MergeBulkFilter.model_fields}
        return MergeBulkFilter(**fields)
    except Exception as exc:  # noqa: BLE001 — bad shape degrades to "uninterpretable"
        logger.warning("Merge bulk-filter compile failed: %s", exc)
        return None
