"""Provider C — "Cobalt Directory".

Transport: POST search with cursor pagination.   POST /api/directory/search
Auth:      Bearer token.   Authorization: Bearer ...
Shape:     name as a nested {given, family} object, email under contact.email
           (sometimes with stray whitespace), role/department under assignment,
           lowercase lifecycle_status, pay as {value, unit, iso_currency},
           hire date as a **DD/MM/YYYY** string.

Run:  uvicorn mock_apis.provider_c:app --port 9003 --reload
Docs: http://localhost:9003/docs
"""

from __future__ import annotations

import os

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field

BEARER_TOKEN = os.environ.get("COBALT_TOKEN", "cobalt-bearer-token")

_bearer = HTTPBearer(auto_error=False)


def require_bearer(
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    if creds is None or creds.credentials != BEARER_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid bearer token. Send 'Authorization: Bearer <token>'.",
        )


# --- Seed data, in Cobalt's own shape ------------------------------------------------
PEOPLE: list[dict] = [
    {
        "uuid": "cobalt-9f3a2b",
        "name": {"given": "María", "family": "González"},
        "contact": {"email": "maria.gonzalez@acme.com ", "phone": "+52 55 1234 5678"},
        "assignment": {"role": "Software Engineer", "org_unit": "Engineering Dept"},
        "lifecycle_status": "employed",
        "pay": {"value": 840000, "unit": "year", "iso_currency": "MXN"},
        "joined": "15/03/2021",
    },
    {
        "uuid": "cobalt-1c4d",
        "name": {"given": "James", "family": "Smith"},
        "contact": {"email": "James.Smith@acme.com", "phone": "+52 55 2222 3333"},
        "assignment": {"role": "Product Manager", "org_unit": "Product Team"},
        "lifecycle_status": "employed",
        "pay": {"value": 960000, "unit": "year", "iso_currency": "MXN"},
        "joined": "01/07/2019",
    },
    {
        "uuid": "cobalt-7e8f",
        "name": {"given": "Yuki", "family": "Tanaka"},
        "contact": {"email": " yuki.tanaka@acme.com", "phone": "+52 55 4444 5555"},
        "assignment": {"role": "Data Analyst", "org_unit": "Data"},
        "lifecycle_status": "employed",
        "pay": {"value": 720000, "unit": "year", "iso_currency": "MXN"},
        "joined": "10/01/2022",
    },
    {
        "uuid": "cobalt-3a2b",
        "name": {"given": "David", "family": "Cohen"},
        "contact": {"email": "david.cohen@acme.com", "phone": "+52 55 6666 7777"},
        "assignment": {"role": "Sales Executive", "org_unit": "Sales"},
        "lifecycle_status": "employed",
        "pay": {"value": 690000, "unit": "year", "iso_currency": "MXN"},
        "joined": "06/06/2022",
    },
    {
        "uuid": "cobalt-5d6e",
        "name": {"given": "Fatima", "family": "Noor"},
        "contact": {"email": "fatima.noor@acme.com", "phone": "+52 55 8888 9999"},
        "assignment": {"role": "Customer Success Manager", "org_unit": "Customer Success"},
        "lifecycle_status": "former",
        "pay": {"value": 750000, "unit": "year", "iso_currency": "MXN"},
        "joined": "22/08/2016",
    },
]


class SearchRequest(BaseModel):
    limit: int = Field(2, ge=1, le=100, description="Page size (small by design)")
    cursor: str | None = Field(
        None, description="Opaque cursor from the previous response; omit for page 1"
    )
    filters: dict | None = Field(None, description="Reserved; ignored by this mock")


app = FastAPI(
    title="Cobalt Directory (Provider C)",
    description="Mock HR provider. POST search with cursor pagination, Bearer auth.",
    version="2024-05",
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "provider": "cobalt"}


@app.post("/api/directory/search", dependencies=[Depends(require_bearer)])
def search(body: SearchRequest) -> dict:
    """Cursor-paginated people search. Pass the returned `cursor` back to fetch the
    next page; a null `cursor` means there are no more results."""
    try:
        offset = int(body.cursor) if body.cursor else 0
    except ValueError:
        raise HTTPException(status_code=400, detail="Malformed cursor")
    window = PEOPLE[offset : offset + body.limit]
    next_offset = offset + body.limit
    next_cursor = str(next_offset) if next_offset < len(PEOPLE) else None
    return {"results": window, "cursor": next_cursor}
