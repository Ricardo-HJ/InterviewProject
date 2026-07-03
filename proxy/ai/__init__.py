"""AI layer.

A thin, optional wrapper around the Anthropic Messages API. Everything here
degrades gracefully: if no API key is configured (or a call fails), helpers
return ``None`` and callers fall back to their deterministic result.
"""

from __future__ import annotations

from .bulk_actions import compile_conflict_filter, compile_merge_filter
from .classify import refine_titles
from .client import ai_available, ask_json
from .merge_sim import MergeSimulation, simulate_merge
from .nlquery import compile_query
from .rootcause import explain_issue
from .schema_infer import SchemaMapping, apply_mapping, infer_mapping
from .summarize import summarize_employee

__all__ = [
    "ask_json",
    "ai_available",
    "refine_titles",
    "compile_query",
    "compile_conflict_filter",
    "compile_merge_filter",
    "summarize_employee",
    "explain_issue",
    "simulate_merge",
    "MergeSimulation",
    "infer_mapping",
    "apply_mapping",
    "SchemaMapping",
]
