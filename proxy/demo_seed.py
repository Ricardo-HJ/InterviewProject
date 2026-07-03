"""Synthetic near-duplicate(s) for demonstrating fuzzy dedup.

The mock providers are read-only and their real cross-provider duplicates all match
cleanly on ``(email, hire_date)``, so exact dedup leaves no fuzzy work. To show a genuine
fuzzy catch we inject ONE deliberately-perturbed near-duplicate of a real single-provider
seed person (Carlos Ruiz): a different provider, a typo'd surname and email, an
abbreviated title — the same human, just entered messily in another system.

Gated by ``config.FUZZY_DEMO_SEED`` (on by default; set ``FUZZY_DEMO_SEED=0`` to disable).
"""

from __future__ import annotations

from decimal import Decimal

import transform
from models import Employee, build_single_provider_employee


def demo_records() -> list[Employee]:
    """Perturbed near-duplicate of carlos.ruiz@acme.com (real Atlas single-provider seed).

    Differences vs the real record: provider beacon (not atlas), surname Ruis/Ruiz,
    email ...ruis/...ruiz, title abbreviated — but the SAME hire date and department.
    Exact dedup misses it (different email); fuzzy dedup should rank it as a top match.
    """
    carlos_duplicate = build_single_provider_employee(
        provider="beacon",
        provider_id="demo-5099",
        email="carlos.ruis@acme.com",
        name=("Carlos Ruis", "Carlos Ruis"),
        # Same canonicalization the real providers apply: the raw stays abbreviated
        # ("DevOps Eng.") for provenance, the canonical value reads "DevOps Engineer".
        title=(transform.canonical_title("DevOps Eng."), "DevOps Eng."),
        department=("Engineering", "Engineering"),
        salary_annual=(Decimal("1080000.00"), 108000000),
        currency="MXN",
        hire_date=("2018-05-14", "2018-05-14"),
        status=("ACTIVE", "ACTIVE"),
    )
    return [carlos_duplicate]
