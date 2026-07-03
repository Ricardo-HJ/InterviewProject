from __future__ import annotations

import httpx

import config
import transform
from models import Employee, build_single_provider_employee

NAME = "atlas"


async def fetch(client: httpx.AsyncClient) -> list[dict]:
    """Walk every page until we've collected ``total`` records."""
    headers = {"X-API-Key": config.ATLAS_API_KEY}
    url = f"{config.ATLAS.base_url}/v1/employees"
    out: list[dict] = []
    page = 1
    while True:
        resp = await client.get(
            url,
            params={"page": page, "per_page": config.PAGE_SIZE},
            headers=headers,
            timeout=config.ATLAS.timeout_seconds,
        )
        resp.raise_for_status()
        body = resp.json()
        out.extend(body["data"])
        if page * body["per_page"] >= body["total"]:
            break
        page += 1
    return out


def normalize(rec: dict) -> Employee:
    return build_single_provider_employee(
        provider=NAME,
        provider_id=rec["id"],
        email=transform.clean_email(rec["work_email"]),
        name=(
            f'{rec["first_name"]} {rec["last_name"]}'.strip(),
            {"first_name": rec["first_name"], "last_name": rec["last_name"]},
        ),
        title=(transform.canonical_title(rec["job_title"]), rec["job_title"]),
        department=(transform.canonical_department(rec["department"]), rec["department"]),
        salary_annual=(
            transform.to_annual_from_cents(rec["annual_salary_cents"]),
            rec["annual_salary_cents"],
        ),
        currency=rec.get("currency"),
        hire_date=(transform.iso_from_iso(rec["hire_date"]), rec["hire_date"]),
        status=(transform.atlas_status(rec["employment_status"]), rec["employment_status"]),
    )
