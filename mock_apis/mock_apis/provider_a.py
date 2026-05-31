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

API_KEY = os.environ.get("ATLAS_API_KEY", "atlas-secret-key")

_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def require_api_key(key: str | None = Depends(_api_key_header)) -> None:
    if key != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid API key. Send it in the 'X-API-Key' header.",
        )


# --- Seed data, in Atlas's own shape -------------------------------------------------
EMPLOYEES: list[dict] = [
    {
        "id": "A-1001",
        "first_name": "María",
        "last_name": "González",
        "work_email": "maria.gonzalez@acme.com",
        "job_title": "Software Engineer",
        "department": "Engineering",
        "employment_status": "ACTIVE",
        "annual_salary_cents": 84000000,
        "currency": "MXN",
        "hire_date": "2021-03-15",
    },
    {
        "id": "A-1002",
        "first_name": "James",
        "last_name": "Smith",
        "work_email": "james.smith@acme.com",
        "job_title": "Product Manager",
        "department": "Product",
        "employment_status": "ACTIVE",
        "annual_salary_cents": 96000000,
        "currency": "MXN",
        "hire_date": "2019-07-01",
    },
    {
        "id": "A-1003",
        "first_name": "Aisha",
        "last_name": "Khan",
        "work_email": "aisha.khan@acme.com",
        "job_title": "Designer",
        "department": "Design",
        "employment_status": "ACTIVE",
        "annual_salary_cents": 78000000,
        "currency": "MXN",
        "hire_date": "2020-11-23",
    },
    {
        "id": "A-1004",
        "first_name": "Carlos",
        "last_name": "Ruiz",
        "work_email": "carlos.ruiz@acme.com",
        "job_title": "DevOps Engineer",
        "department": "Engineering",
        "employment_status": "ACTIVE",
        "annual_salary_cents": 90000000,
        "currency": "MXN",
        "hire_date": "2018-05-14",
    },
    {
        "id": "A-1005",
        "first_name": "Emma",
        "last_name": "Brown",
        "work_email": "emma.brown@acme.com",
        "job_title": "Recruiter",
        "department": "People",
        "employment_status": "ON_LEAVE",
        "annual_salary_cents": 60000000,
        "currency": "MXN",
        "hire_date": "2023-02-01",
    },
]

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
