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

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyQuery

from .sample_data import beacon_staff
from .seed_data import BEACON_STAFF

API_KEY = os.environ.get("BEACON_API_KEY", "beacon-key-123")

_api_key_query = APIKeyQuery(name="api_key", auto_error=False)


def require_api_key(api_key: str | None = Depends(_api_key_query)) -> None:
    if api_key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key. Pass it as the 'api_key' query parameter.",
        )


STAFF: list[dict] = [*BEACON_STAFF]
STAFF.extend(beacon_staff(seed_count=len(STAFF)))

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
