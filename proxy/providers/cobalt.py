from __future__ import annotations

import httpx

import config
import transform
from models import Employee, build_single_provider_employee

NAME = "cobalt"


async def fetch(client: httpx.AsyncClient) -> list[dict]:
    """Feed the returned cursor back until it comes back null."""
    headers = {"Authorization": f"Bearer {config.COBALT_TOKEN}"}
    url = f"{config.COBALT.base_url}/api/directory/search"
    out: list[dict] = []
    cursor: str | None = None
    while True:
        payload: dict = {"limit": config.PAGE_SIZE}
        if cursor is not None:
            payload["cursor"] = cursor
        resp = await client.post(
            url, json=payload, headers=headers, timeout=config.COBALT.timeout_seconds
        )
        resp.raise_for_status()
        body = resp.json()
        out.extend(body["results"])
        cursor = body.get("cursor")
        if cursor is None:
            break
    return out


def normalize(rec: dict) -> Employee:
    name = rec["name"]
    contact = rec.get("contact") or {}
    assignment = rec.get("assignment") or {}
    pay = rec["pay"]
    return build_single_provider_employee(
        provider=NAME,
        provider_id=rec["uuid"],
        email=transform.clean_email(contact.get("email")),
        name=(
            f'{name["given"]} {name["family"]}'.strip(),
            {"given": name["given"], "family": name["family"]},
        ),
        title=(transform.canonical_title(assignment.get("role")), assignment.get("role")),
        department=(transform.canonical_department(assignment.get("org_unit")), assignment.get("org_unit")),
        salary_annual=(transform.to_annual_from_year(pay["value"]), pay),
        currency=pay.get("iso_currency"),
        hire_date=(transform.iso_from_ddmmyyyy(rec["joined"]), rec["joined"]),
        status=(transform.cobalt_status(rec["lifecycle_status"]), rec["lifecycle_status"]),
    )
