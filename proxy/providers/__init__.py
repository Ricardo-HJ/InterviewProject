from __future__ import annotations

from . import atlas, beacon, cobalt

# Registry consumed by main.py — keeps the endpoint provider-agnostic.
PROVIDERS = (atlas, beacon, cobalt)

__all__ = ["atlas", "beacon", "cobalt", "PROVIDERS"]
