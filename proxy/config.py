from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ProviderSettings:
    name: str
    base_url: str
    timeout_seconds: float = 10.0


ATLAS = ProviderSettings(
    name="atlas",
    base_url=os.environ.get("ATLAS_BASE_URL", "http://localhost:9001"),
)
BEACON = ProviderSettings(
    name="beacon",
    base_url=os.environ.get("BEACON_BASE_URL", "http://localhost:9002"),
)
COBALT = ProviderSettings(
    name="cobalt",
    base_url=os.environ.get("COBALT_BASE_URL", "http://localhost:9003"),
)

# Credentials (defaults match .env.example so local dev works out of the box).
ATLAS_API_KEY = os.environ.get("ATLAS_API_KEY", "atlas-secret-key")
BEACON_API_KEY = os.environ.get("BEACON_API_KEY", "beacon-key-123")
COBALT_TOKEN = os.environ.get("COBALT_TOKEN", "cobalt-bearer-token")

PAGE_SIZE = 100

CACHE_TTL_SECONDS = float(os.environ.get("PROXY_CACHE_TTL", "30"))


# --- AI layer ----------------------------------------------------------------
# The whole AI layer degrades gracefully: with no key, AI_ENABLED is False and
# every AI feature falls back to its deterministic result (see ai/client.py).
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
AI_ENABLED = bool(ANTHROPIC_API_KEY)


AI_MODEL_FAST = os.environ.get("AI_MODEL_FAST", "claude-haiku-4-5")
AI_MODEL_REASON = os.environ.get("AI_MODEL_REASON", "claude-sonnet-4-6")

AI_TIMEOUT_SECONDS = float(os.environ.get("AI_TIMEOUT", "20"))
AI_MAX_RETRIES = int(os.environ.get("AI_MAX_RETRIES", "2"))


# --- Fuzzy dedup demo --------------------------------------------------------
# The mock providers' real cross-provider duplicates all match cleanly on
# (email, hire_date), so exact dedup leaves no fuzzy work to show. When enabled we
# inject ONE deliberately-perturbed near-duplicate of a real seed person so the
# /merge-candidates demo has a genuine catch. Set FUZZY_DEMO_SEED=0 for pure real data.
FUZZY_DEMO_SEED = os.environ.get("FUZZY_DEMO_SEED", "1").lower() not in ("0", "false", "")

# --- Self-healing schema mapping (stretch) -----------------------------------
# When a provider's hand-written normalizer fails (e.g. an upstream renamed a field),
# fall back to LLM-inferred schema mapping instead of silently dropping the records.
# This is purely additive: it ONLY runs when a normalizer raises (never for the static
# mocks) and needs the AI layer, so with no key it's a no-op and records skip as before.
# Set SELF_HEAL_SCHEMA=0 to remove the fallback path entirely.
SELF_HEAL_SCHEMA = os.environ.get("SELF_HEAL_SCHEMA", "1").lower() not in ("0", "false", "")
