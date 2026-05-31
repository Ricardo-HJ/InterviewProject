"""Provider B — "Beacon People".

Transport: full list + fetch-by-id.   GET /staff   and   GET /staff/{staff_id}
Auth:      api_key query parameter.   ?api_key=...
Shape:     single full_name string, email (varying case), position, team as a nested
           object, status split across two booleans (is_active / on_leave),
           compensation as a nested object with a **monthly** decimal-string amount,
           hire time as a **unix-milliseconds** integer.

Run:  uvicorn mock_apis.provider_b:app --port 9002 --reload
Docs: http://localhost:9002/docs
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import APIKeyQuery

API_KEY = os.environ.get("BEACON_API_KEY", "beacon-key-123")

_api_key_query = APIKeyQuery(name="api_key", auto_error=False)


def require_api_key(api_key: str | None = Depends(_api_key_query)) -> None:
    if api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key. Pass it as the 'api_key' query parameter.",
        )


def _unix_ms(iso_date: str) -> int:
    dt = datetime.strptime(iso_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


# --- Seed data, in Beacon's own shape ------------------------------------------------
STAFF: list[dict] = [
    {
        "staff_id": 5001,
        "full_name": "Maria Gonzalez",
        "email": "MARIA.GONZALEZ@acme.com",
        "position": "Sr. Software Engineer",
        "team": {"id": 12, "name": "Engineering"},
        "is_active": True,
        "on_leave": False,
        "compensation": {"amount": "70000.00", "period": "monthly", "currency": "MXN"},
        "started_at": _unix_ms("2021-03-15"),
    },
    {
        "staff_id": 5002,
        "full_name": "Yuki Tanaka",
        "email": "yuki.tanaka@acme.com",
        "position": "Data Analyst",
        "team": {"id": 8, "name": "Data"},
        "is_active": True,
        "on_leave": True,
        "compensation": {"amount": "60000.00", "period": "monthly", "currency": "MXN"},
        "started_at": _unix_ms("2022-01-10"),
    },
    {
        "staff_id": 5003,
        "full_name": "Aisha Khan",
        "email": "Aisha.Khan@ACME.com",
        "position": "Senior Designer",
        "team": {"id": 5, "name": "Design"},
        "is_active": True,
        "on_leave": False,
        "compensation": {"amount": "65000.00", "period": "monthly", "currency": "MXN"},
        "started_at": _unix_ms("2020-11-23"),
    },
    {
        "staff_id": 5004,
        "full_name": "Liang Wei",
        "email": "liang.wei@acme.com",
        "position": "Backend Engineer",
        "team": {"id": 12, "name": "Engineering"},
        "is_active": True,
        "on_leave": False,
        "compensation": {"amount": "72500.00", "period": "monthly", "currency": "MXN"},
        "started_at": _unix_ms("2021-09-30"),
    },
    {
        "staff_id": 5005,
        "full_name": "Sofia Rossi",
        "email": "sofia.rossi@acme.com",
        "position": "Marketing Lead",
        "team": {"id": 3, "name": "Marketing"},
        "is_active": True,
        "on_leave": False,
        "compensation": {"amount": "67500.00", "period": "monthly", "currency": "MXN"},
        "started_at": _unix_ms("2017-03-19"),
    },
]

app = FastAPI(
    title="Beacon People (Provider B)",
    description="Mock HR provider. Plain list + by-id, api_key query-param auth.",
    version="2.3.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": "beacon"}


@app.get("/staff", dependencies=[Depends(require_api_key)])
def list_staff() -> list[dict]:
    """Return the full staff list (no pagination)."""
    return STAFF


@app.get("/staff/{staff_id}", dependencies=[Depends(require_api_key)])
def get_staff(staff_id: int) -> dict:
    for member in STAFF:
        if member["staff_id"] == staff_id:
            return member
    raise HTTPException(status_code=404, detail="Staff member not found")
