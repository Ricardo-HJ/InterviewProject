from __future__ import annotations

import json
import logging
from typing import Any

import config

logger = logging.getLogger("proxy.ai")

try:  # The dependency is declared, but never let an import problem break the app.
    from anthropic import AsyncAnthropic
except Exception:  # pragma: no cover
    AsyncAnthropic = None  # type: ignore[assignment]

_client: "AsyncAnthropic | None" = None

# Default nudge for the no-schema path so the model returns parseable JSON.
_JSON_SYSTEM = "Respond with a single valid JSON value and nothing else — no prose, no code fences."


def _get_client() -> "AsyncAnthropic | None":
    """Lazily build the shared async client, or return None if AI is disabled."""
    global _client
    if not config.AI_ENABLED or AsyncAnthropic is None:
        return None
    if _client is None:
        _client = AsyncAnthropic(
            api_key=config.ANTHROPIC_API_KEY,
            timeout=config.AI_TIMEOUT_SECONDS,
            max_retries=config.AI_MAX_RETRIES,
        )
    return _client


def ai_available() -> bool:
    """True when an API key is configured and the SDK is importable."""
    return _get_client() is not None


def _parse_json(text: str) -> Any | None:
    """Parse model output as JSON, salvaging the first JSON value if needed."""
    text = (text or "").strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except Exception:
        for opener, closer in (("{", "}"), ("[", "]")):
            start, end = text.find(opener), text.rfind(closer)
            if 0 <= start < end:
                try:
                    return json.loads(text[start : end + 1])
                except Exception:
                    continue
    return None


async def ask_json(
    prompt: str,
    *,
    schema: dict | None = None,
    system: str | None = None,
    model: str | None = None,
    max_tokens: int = 1024,
) -> Any | None:
    """Ask Claude for a JSON answer; return the parsed value or ``None``.

    Returns ``None`` (never raises) when AI is disabled or the call/parse fails,
    so callers can simply do ``result = await ask_json(...) or deterministic()``.

    ``schema`` should be a JSON Schema with ``additionalProperties: false`` and a
    ``required`` list (Anthropic structured-output requirement). Omit it to let
    the model free-form a JSON value, which we then parse defensively.
    """
    model = model or config.AI_MODEL_FAST
    client = _get_client()
    if client is None:
        return None

    effective_system = system or (None if schema is not None else _JSON_SYSTEM)
    try:
        kwargs: dict[str, Any] = {
            "model": model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if effective_system:
            kwargs["system"] = effective_system
        if schema is not None:
            kwargs["output_config"] = {
                "format": {"type": "json_schema", "schema": schema}
            }
        resp = await client.messages.create(**kwargs)
        text = next(
            (b.text for b in resp.content if getattr(b, "type", None) == "text"),
            "",
        )
        data = _parse_json(text)
    except Exception as exc:  # noqa: BLE001 — any failure degrades to deterministic
        logger.warning("AI call failed (model=%s): %s", model, exc)
        return None

    return data
