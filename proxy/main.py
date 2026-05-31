"""Proxy (BFF) — STARTER SKELETON.

This is intentionally almost empty. Your task is to turn this into a proxy that:
  1. fetches employees from the three Provider APIs,
  2. normalizes each Provider's shape into one canonical Employee model you design,
  3. resolves duplicate people that appear across Providers and merges them,
  4. exposes the result to the frontend.

See the top-level README.md for the Provider URLs and credentials. Structure the
code however you think is best — there are no required files or function names.

Run:  uv run uvicorn main:app --port 8000 --reload
Docs: http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Employee Aggregator Proxy")

# Open CORS for local frontend dev — not part of the exercise, leave as-is.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


# TODO(candidate): build the aggregation endpoint(s) here.
