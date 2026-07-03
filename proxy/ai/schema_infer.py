from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ValidationError

import config
import transform
from models import Employee, build_single_provider_employee

from .client import ai_available, ask_json

logger = logging.getLogger("proxy.ai")

# Closed transform vocabularies — each value corresponds to one helper in transform.py.
SalaryUnit = Literal["annual_cents", "annual_major", "monthly", "annual_year"]
DateFormat = Literal["iso", "unix_ms", "ddmmyyyy"]
StatusMode = Literal["upper_enum", "lower_enum", "active_leave_booleans"]
NameMode = Literal["full", "given_family"]


class SchemaMapping(BaseModel):
    """A flat field map from a provider's raw shape onto the canonical Employee.

    Paths are dot-notation into the raw record (e.g. ``pay_info.amount``). Optional
    paths default to ``""`` (never ``None``) so the model stays plain-typed.
    """

    provider_id_path: str
    email_path: str
    name_mode: NameMode
    name_path: str
    name_family_path: str = ""  # only used when name_mode == "given_family"
    title_path: str
    department_path: str
    salary_path: str
    salary_unit: SalaryUnit
    currency_path: str = ""
    hire_date_path: str
    hire_date_format: DateFormat
    status_mode: StatusMode
    status_path: str
    status_secondary_path: str = ""  # the on_leave path for active_leave_booleans


def _dig(rec: Any, path: str) -> Any:
    """Resolve a dot-notation path into a nested dict; missing → ``None``."""
    if not path:
        return None
    cur = rec
    for part in path.split("."):
        if isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
    return cur


def _salary(value: Any, unit: SalaryUnit) -> Decimal | None:
    if value is None:
        return None
    if unit == "annual_cents":
        return transform.to_annual_from_cents(int(value))
    if unit == "monthly":
        return transform.to_annual_from_monthly(value)
    if unit == "annual_year":
        return transform.to_annual_from_year(value)
    # annual_major: already annual in major units, just quantize like the others.
    return Decimal(str(value)).quantize(Decimal("0.01"))


def _hire_date(value: Any, fmt: DateFormat) -> str | None:
    if value is None or value == "":
        return None
    if fmt == "unix_ms":
        return transform.iso_from_unix_ms(int(value))
    if fmt == "ddmmyyyy":
        return transform.iso_from_ddmmyyyy(str(value))
    return transform.iso_from_iso(str(value))


def _status(mapping: SchemaMapping, rec: Any):
    primary = _dig(rec, mapping.status_path)
    if mapping.status_mode == "active_leave_booleans":
        secondary = _dig(rec, mapping.status_secondary_path)
        return transform.beacon_status(bool(primary), bool(secondary))
    if mapping.status_mode == "lower_enum":
        return transform.cobalt_status(str(primary or ""))
    return transform.atlas_status(str(primary or ""))


def apply_mapping(mapping: SchemaMapping, rec: dict, *, provider: str) -> Employee:
    """Build a canonical Employee from a raw record using ``mapping``. Pure/deterministic."""
    if mapping.name_mode == "given_family":
        given, family = _dig(rec, mapping.name_path), _dig(rec, mapping.name_family_path)
        name_value = f"{given or ''} {family or ''}".strip()
        name_raw: Any = {"given": given, "family": family}
    else:
        name_value = _dig(rec, mapping.name_path)
        name_raw = name_value

    salary_raw = _dig(rec, mapping.salary_path)
    title_raw = _dig(rec, mapping.title_path)
    dept_raw = _dig(rec, mapping.department_path)
    hire_raw = _dig(rec, mapping.hire_date_path)

    return build_single_provider_employee(
        provider=provider,  # type: ignore[arg-type]
        provider_id=str(_dig(rec, mapping.provider_id_path)),
        email=transform.clean_email(_dig(rec, mapping.email_path)),
        name=(name_value, name_raw),
        title=(transform.canonical_title(title_raw), title_raw),
        department=(transform.canonical_department(dept_raw), dept_raw),
        salary_annual=(_salary(salary_raw, mapping.salary_unit), salary_raw),
        currency=_dig(rec, mapping.currency_path),
        hire_date=(_hire_date(hire_raw, mapping.hire_date_format), hire_raw),
        status=(_status(mapping, rec), _dig(rec, mapping.status_path)),
    )


_SYSTEM = (
    "You infer how to map one HR provider's raw record shape onto a fixed canonical "
    "employee schema. You are given sample raw record(s). Return a JSON object whose "
    "fields are DOT-NOTATION paths into the raw record, plus a few transform selectors. "
    "Canonical fields and the JSON keys to return:\n"
    "- provider_id_path: path to the provider's native id\n"
    "- email_path: path to the email\n"
    "- name_mode: 'full' if one field holds the whole name, else 'given_family'\n"
    "- name_path: path to full name (or to the given/first name)\n"
    "- name_family_path: path to the family/last name (only for 'given_family', else \"\")\n"
    "- title_path, department_path: paths to job title and team/department name\n"
    "- salary_path: path to the salary amount\n"
    "- salary_unit: one of 'annual_cents' (integer annual cents), 'annual_major' "
    "(already annual in major units), 'monthly' (monthly amount), 'annual_year' (annual)\n"
    "- currency_path: path to the currency code (or \"\")\n"
    "- hire_date_path: path to the hire date\n"
    "- hire_date_format: one of 'iso' (YYYY-MM-DD), 'unix_ms' (unix milliseconds), "
    "'ddmmyyyy' (DD/MM/YYYY)\n"
    "- status_mode: one of 'upper_enum' (UPPERCASE string), 'lower_enum' (lowercase "
    "string), 'active_leave_booleans' (two booleans: active + on-leave)\n"
    "- status_path: path to the status value (or to the 'active' boolean)\n"
    "- status_secondary_path: path to the 'on_leave' boolean (only for "
    "'active_leave_booleans', else \"\")\n"
    "Infer paths and selectors ONLY from the sample provided. Return JSON only, no prose."
)


async def infer_mapping(provider_name: str, sample_records: list[dict]) -> SchemaMapping | None:
    """Infer a ``SchemaMapping`` for a provider from sample raw records.

    Returns ``None`` when AI is unavailable or the response can't be validated — the
    caller then falls back to skipping the unparseable records (today's behavior).
    """
    if not sample_records or not ai_available():
        return None

    sample = sample_records[:2]
    prompt = (
        f"Provider: {provider_name}\nSample raw record(s):\n"
        + json.dumps(sample, ensure_ascii=False, default=str)
    )
    data = await ask_json(
        prompt,
        system=_SYSTEM,
        model=config.AI_MODEL_REASON,
        max_tokens=768,
    )
    if not isinstance(data, dict):
        return None
    try:
        fields = {k: v for k, v in data.items() if k in SchemaMapping.model_fields}
        return SchemaMapping(**fields)
    except ValidationError as exc:
        logger.warning("Schema mapping for %s had unexpected shape: %s", provider_name, exc)
        return None
