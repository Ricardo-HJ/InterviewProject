from __future__ import annotations

import json
import logging

from pydantic import BaseModel, Field, ValidationError

import config
from fuzzy import MergeCandidate

from .client import ai_available, ask_json

logger = logging.getLogger("proxy.ai")


class MergeEffect(BaseModel):
    """One predicted consequence of the merge (``ok`` = benign vs needs attention)."""

    label: str
    ok: bool


class MergeRisk(BaseModel):
    """One area a human should verify before approving."""

    area: str
    note: str


class MergeSimulation(BaseModel):
    summary: str
    effects: list[MergeEffect] = Field(default_factory=list)
    risks: list[MergeRisk] = Field(default_factory=list)


_SYSTEM = (
    "You are an HR data assistant. You are given two employee records that a reviewer is "
    "considering merging as the same person, plus per-field similarity signals (0..1). "
    "Predict the consequences of merging them and flag what a human should verify. Use "
    "ONLY the data provided — do not invent fields, payroll systems, or facts not present. "
    "Respond with a JSON object: 'summary' (1-2 sentences), 'effects' (array of "
    "{label, ok} where ok=true means a benign/expected outcome and ok=false means it "
    "needs attention), and 'risks' (array of {area, note} for things to verify). Keep "
    "each list short and specific."
)

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "effects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "label": {"type": "string"},
                    "ok": {"type": "boolean"},
                },
                "required": ["label", "ok"],
                "additionalProperties": False,
            },
        },
        "risks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "area": {"type": "string"},
                    "note": {"type": "string"},
                },
                "required": ["area", "note"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "effects", "risks"],
    "additionalProperties": False,
}


def build_merge_context(c: MergeCandidate) -> dict:
    """Both sides + signals + which fields differ, for the simulation prompt. Pure."""
    fields = ("name", "email", "title", "department", "hire_date")
    differing = [
        f for f in fields if str(getattr(c.left, f)) != str(getattr(c.right, f))
    ]
    return {
        "score": c.score,
        "signals": c.signals,
        "differing_fields": differing,
        "left": c.left.model_dump(mode="json"),
        "right": c.right.model_dump(mode="json"),
    }


async def simulate_merge(c: MergeCandidate) -> MergeSimulation | None:
    """Return a structured impact analysis, or ``None`` if AI is off/failed."""
    if not ai_available():
        return None

    prompt = "Simulate merging these two records:\n" + json.dumps(
        build_merge_context(c), ensure_ascii=False
    )
    data = await ask_json(
        prompt,
        schema=_SCHEMA,
        system=_SYSTEM,
        model=config.AI_MODEL_REASON,
        max_tokens=768,
    )
    if not isinstance(data, dict):
        return None
    try:
        return MergeSimulation(**data)
    except ValidationError as exc:
        logger.warning("Merge simulation had unexpected shape: %s", exc)
        return None
