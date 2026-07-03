from __future__ import annotations

import httpx

import config
import transform
from models import Employee, build_single_provider_employee

NAME = "beacon"


async def fetch(client: httpx.AsyncClient) -> list[dict]:
    resp = await client.get(
        f"{config.BEACON.base_url}/staff",
        params={"api_key": config.BEACON_API_KEY},
        timeout=config.BEACON.timeout_seconds,
    )
    resp.raise_for_status()
    return resp.json()


def normalize(rec: dict) -> Employee:
    comp = rec["compensation"]
    team = rec.get("team") or {}
    return build_single_provider_employee(
        provider=NAME,
        provider_id=str(rec["staff_id"]),
        email=transform.clean_email(rec["email"]),
        name=(rec["full_name"], rec["full_name"]),
        title=(transform.canonical_title(rec["position"]), rec["position"]),
        department=(transform.canonical_department(team.get("name")), team),
        salary_annual=(
            transform.to_annual_from_monthly(comp["amount"]),
            {"amount": comp["amount"], "period": comp.get("period")},
        ),
        currency=comp.get("currency"),
        hire_date=(transform.iso_from_unix_ms(rec["started_at"]), rec["started_at"]),
        status=(
            transform.beacon_status(rec["is_active"], rec["on_leave"]),
            {"is_active": rec["is_active"], "on_leave": rec["on_leave"]},
        ),
    )
