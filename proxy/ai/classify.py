from __future__ import annotations

import json
import logging

import config
from titles import FAMILIES, LEVELS, CanonicalTitle

from .client import ai_available, ask_json

logger = logging.getLogger("proxy.ai")

MAX_TITLES = 120  # cap distinct titles per request

_SYSTEM = (
    "You map messy HR job titles onto a small controlled taxonomy. For each title return: "
    "'role' = the canonical role with seniority words removed (e.g. 'Software Engineer' for "
    "'Sr. Software Engineer'); 'family' = exactly one of " + ", ".join(FAMILIES) + "; and "
    "'level' = exactly one of " + ", ".join(LEVELS) + ". Judge level from seniority words, "
    "NOT from role nouns: 'Account Manager', 'Product Manager', 'Customer Success Manager' "
    "are individual-contributor roles at Mid level — reserve 'Manager'/'Director' for actual "
    "people-management titles. Return JSON only."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "mappings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "role": {"type": "string"},
                    "family": {"type": "string", "enum": list(FAMILIES)},
                    "level": {"type": "string", "enum": list(LEVELS)},
                },
                "required": ["title", "role", "family", "level"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["mappings"],
    "additionalProperties": False,
}


async def refine_titles(raw_titles: list[str]) -> dict[str, CanonicalTitle]:
    """Return ``{raw_title -> CanonicalTitle(source="ai")}`` for titles the LLM mapped.

    Empty dict when AI is unavailable or the call fails — callers fall back to the
    deterministic mapping. Never raises.
    """
    if not raw_titles or not ai_available():
        return {}

    batch = raw_titles[:MAX_TITLES]
    prompt = "Normalize each title:\n" + json.dumps(batch, ensure_ascii=False)

    data = await ask_json(
        prompt,
        schema=_SCHEMA,
        system=_SYSTEM,
        model=config.AI_MODEL_FAST,
        max_tokens=4096,
    )
    if not isinstance(data, dict) or "mappings" not in data:
        return {}

    valid_titles = set(batch)
    out: dict[str, CanonicalTitle] = {}
    for item in data["mappings"]:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        role = item.get("role")
        family = item.get("family")
        level = item.get("level")
        if title not in valid_titles or not role:
            continue
        if family not in FAMILIES or level not in LEVELS:
            continue
        out[title] = CanonicalTitle(role=role, family=family, level=level, source="ai")
    if out:
        logger.info("AI normalized %d/%d titles", len(out), len(batch))
    return out
