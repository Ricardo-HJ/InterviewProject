"""Provider A — "Atlas HR".

Transport: paginated REST list.   GET /v1/employees?page=&per_page=
Auth:      X-API-Key header.
Shape:     flat record, split first/last name, salary as integer **cents**,
           ISO-8601 hire date, UPPERCASE status enum, department as a string.

Run:  uvicorn mock_apis.provider_a:app --port 9001 --reload
Docs: http://localhost:9001/docs
"""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.security import APIKeyHeader

from .sample_data import atlas_employees
from .seed_data import ATLAS_EMPLOYEES

API_KEY = os.environ.get("ATLAS_API_KEY", "atlas-secret-key")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Depends(_api_key_header)) -> None:
    if key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key. Send it in the 'X-API-Key' header.",
        )


EMPLOYEES: list[dict] = [*ATLAS_EMPLOYEES]
EMPLOYEES.extend(atlas_employees(seed_count=len(EMPLOYEES)))

app = FastAPI(
    title="Atlas HR (Provider A)",
    description="Mock HR provider. Paginated REST, X-API-Key header auth.",
    version="1.0.0",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": "atlas"}


@app.get("/v1/employees", dependencies=[Depends(require_api_key)])
def list_employees(
    page: int = Query(1, ge=1, description="1-based page number"),
    per_page: int = Query(2, ge=1, le=100, description="Page size (small by design)"),
) -> dict:
    """Return a page of employees. Note the small default page size — you'll need to
    paginate to retrieve everyone."""
    start = (page - 1) * per_page
    window = EMPLOYEES[start : start + per_page]
    return {
        "data": window,
        "page": page,
        "per_page": per_page,
        "total": len(EMPLOYEES),
    }
