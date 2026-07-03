from __future__ import annotations

import logging

import config
from query import QueryFilter

from .client import ai_available, ask_json

logger = logging.getLogger("proxy.ai")

_SYSTEM = (
    "You translate a user's request into a JSON filter over employee records. Return a "
    "JSON object containing ONLY the fields the request clearly implies; omit all others. "
    "Allowed fields and types:\n"
    '- department (string), role (string): matched case-insensitively as substrings\n'
    "- status: one of ACTIVE, ON_LEAVE, TERMINATED\n"
    "- hired_after, hired_before: ISO date YYYY-MM-DD (e.g. 'hired after 2021' -> "
    'hired_after "2021-01-01")\n'
    '- provider_count (integer): "only in one provider" -> 1\n'
    "- providers (array of: atlas, beacon, cobalt)\n"
    "- salary_min, salary_max (numbers), limit (integer)\n"
    "Return JSON only, no prose."
)


async def compile_query(text: str) -> QueryFilter | None:
    """Compile free text into a ``QueryFilter`` (or ``None`` if AI is off / uninterpretable)."""
    if not text or not text.strip() or not ai_available():
        return None

    data = await ask_json(
        f"Build a filter for this request:\n{text.strip()}",
        system=_SYSTEM,
        model=config.AI_MODEL_FAST,
        max_tokens=512,
    )
    if not isinstance(data, dict):
        return None
    try:
        fields = {k: v for k, v in data.items() if k in QueryFilter.model_fields}
        return QueryFilter(**fields)
    except Exception as exc:  # noqa: BLE001 — bad shape degrades to "uninterpretable"
        logger.warning("NL query compile failed: %s", exc)
        return None
