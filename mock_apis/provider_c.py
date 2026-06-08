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

from .sample_data import cobalt_people
from .seed_data import COBALT_PEOPLE

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


PEOPLE: list[dict] = [*COBALT_PEOPLE]
PEOPLE.extend(cobalt_people(seed_count=len(PEOPLE)))


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
