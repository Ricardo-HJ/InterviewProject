"""Forced schema-drift samples for the self-healing demo.

The mock providers are static and never change shape, so the live ``/employees``
pipeline never actually exercises the self-healing fallback. These hand-built
payloads simulate "an upstream renamed/moved its fields": each is a record for a
*synthetic new person* whose keys no longer match the provider's hand-written
normalizer, so ``normalize`` raises and the LLM-inferred mapping has to recover it.

Used only by the demo endpoints in ``main.py`` (``/schema-mapping/demo`` and
``/self-heal/recovered``) — never injected into the real provider feeds, so the
Employees/Conflicts views and the core pipeline stay untouched.

Two deliberately *different* shapes so the demo shows the LLM adapting, not pattern-
matching one fixed rename:
- Beacon-style: full name, nested monthly ``pay_info``, unix-ms timestamp, two status
  booleans.
- Atlas-style: split given/surname, integer annual cents, ISO date, UPPERCASE enum.
"""

from __future__ import annotations

# Beacon after a hypothetical rename (compensation→pay_info, started_at→hire_timestamp,
# full_name→display_name, position→job, staff_id→id, team→group, booleans active/leave).
_DRIFTED_BEACON_RECORD = {
    "id": 7400,
    "display_name": "Dana Lopez",
    "email_address": "Dana.Lopez@acme.com",
    "job": "Sr. Data Engineer",
    "group": {"name": "Data"},
    "pay_info": {"amount": "75000.00", "cycle": "monthly", "currency": "MXN"},
    "active": True,
    "leave": True,
    "hire_timestamp": 1610000000000,
}

# Atlas after a different rename (id→employee_ref, first/last→given/surname,
# work_email→contact_email, job_title→role_title, department→org,
# annual_salary_cents→salary_cents_yr, employment_status→state, hire_date→start).
_DRIFTED_ATLAS_RECORD = {
    "employee_ref": "A-9100",
    "given": "Omar",
    "surname": "Haddad",
    "contact_email": "Omar.Haddad@acme.com ",
    "role_title": "Sr. Backend Engineer",
    "org": "Engineering",
    "state": "ACTIVE",
    "salary_cents_yr": 99000000,
    "money": "MXN",
    "start": "2022-05-09",
}

# (provider_name, raw record) — the provider whose normalizer SHOULD handle this shape
# but can't anymore. Order drives the Recovered tab's display order.
DRIFTED_SAMPLES: list[tuple[str, dict]] = [
    ("beacon", _DRIFTED_BEACON_RECORD),
    ("atlas", _DRIFTED_ATLAS_RECORD),
]
