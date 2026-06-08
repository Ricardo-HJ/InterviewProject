"""Deterministic sample data used by the mock HR providers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from random import Random
from typing import Callable

TARGET_RECORD_COUNT = 1_200
RELATED_RECORD_COUNT = 300


@dataclass(frozen=True)
class PersonProfile:
    sequence: int
    first_name: str
    last_name: str
    email: str
    job_title: str
    department: str
    team_id: int
    status: str
    annual_salary_cents: int
    currency: str
    hire_date: str
    phone: str


FIRST_NAMES = [
    "María",
    "James",
    "Aisha",
    "Carlos",
    "Emma",
    "Yuki",
    "Liang",
    "Sofia",
    "David",
    "Fatima",
    "Mateo",
    "Nora",
    "Priya",
    "Omar",
    "Isabella",
    "Lucas",
    "Camila",
    "Ethan",
    "Valentina",
    "Noah",
]

LAST_NAMES = [
    "Gonzalez",
    "Smith",
    "Khan",
    "Ruiz",
    "Brown",
    "Tanaka",
    "Wei",
    "Rossi",
    "Cohen",
    "Noor",
    "Garcia",
    "Patel",
    "Santos",
    "Kim",
    "Martinez",
    "Silva",
    "Nguyen",
    "Wilson",
    "Lopez",
    "Miller",
]

DEPARTMENTS = [
    {
        "name": "Engineering",
        "team_id": 12,
        "cobalt_org_unit": "Engineering Dept",
        "roles": [
            "Software Engineer",
            "Backend Engineer",
            "DevOps Engineer",
            "Frontend Engineer",
        ],
        "salary_range": (780_000_00, 1_350_000_00),
    },
    {
        "name": "Product",
        "team_id": 6,
        "cobalt_org_unit": "Product Team",
        "roles": ["Product Manager", "Product Analyst", "Program Manager"],
        "salary_range": (820_000_00, 1_250_000_00),
    },
    {
        "name": "Design",
        "team_id": 5,
        "cobalt_org_unit": "Design Studio",
        "roles": ["Designer", "Product Designer", "UX Researcher"],
        "salary_range": (650_000_00, 1_050_000_00),
    },
    {
        "name": "Data",
        "team_id": 8,
        "cobalt_org_unit": "Data",
        "roles": ["Data Analyst", "Analytics Engineer", "Data Scientist"],
        "salary_range": (700_000_00, 1_200_000_00),
    },
    {
        "name": "People",
        "team_id": 2,
        "cobalt_org_unit": "People Ops",
        "roles": ["Recruiter", "People Partner", "HR Generalist"],
        "salary_range": (520_000_00, 900_000_00),
    },
    {
        "name": "Marketing",
        "team_id": 3,
        "cobalt_org_unit": "Marketing",
        "roles": ["Marketing Lead", "Content Strategist", "Growth Manager"],
        "salary_range": (600_000_00, 1_000_000_00),
    },
    {
        "name": "Sales",
        "team_id": 4,
        "cobalt_org_unit": "Sales",
        "roles": ["Sales Executive", "Account Manager", "Sales Engineer"],
        "salary_range": (580_000_00, 1_100_000_00),
    },
    {
        "name": "Customer Success",
        "team_id": 9,
        "cobalt_org_unit": "Customer Success",
        "roles": [
            "Customer Success Manager",
            "Implementation Specialist",
            "Support Engineer",
        ],
        "salary_range": (560_000_00, 980_000_00),
    },
]

STATUS_WEIGHTS = ["ACTIVE"] * 18 + ["ON_LEAVE"] * 2 + ["FORMER"]


def _slug(value: str) -> str:
    replacements = {
        "á": "a",
        "é": "e",
        "í": "i",
        "ó": "o",
        "ú": "u",
        "Á": "a",
        "É": "e",
        "Í": "i",
        "Ó": "o",
        "Ú": "u",
    }
    normalized = "".join(replacements.get(char, char) for char in value)
    return "".join(char.lower() for char in normalized if char.isalnum())


def _hire_date(rng: Random) -> str:
    start = date(2015, 1, 1)
    return (start + timedelta(days=rng.randint(0, 3_750))).isoformat()


def _salary(rng: Random, low: int, high: int) -> int:
    step = 2_500_00
    return rng.randrange(low // step, high // step + 1) * step


def _phone(sequence: int) -> str:
    block = 10_000_000 + sequence
    return f"+52 55 {block // 10_000:04d} {block % 10_000:04d}"


def generate_profiles(
    *,
    count: int,
    seed: int,
    sequence_start: int,
    email_namespace: str,
    email_domain: str,
) -> list[PersonProfile]:
    rng = Random(seed)
    profiles: list[PersonProfile] = []

    for offset in range(count):
        sequence = sequence_start + offset
        first_name = rng.choice(FIRST_NAMES)
        last_name = rng.choice(LAST_NAMES)
        department = rng.choice(DEPARTMENTS)
        role = rng.choice(department["roles"])
        email = (
            f"{_slug(first_name)}.{_slug(last_name)}."
            f"{email_namespace}{sequence:04d}@{email_domain}"
        )

        profiles.append(
            PersonProfile(
                sequence=sequence,
                first_name=first_name,
                last_name=last_name,
                email=email,
                job_title=role,
                department=department["name"],
                team_id=department["team_id"],
                status=rng.choice(STATUS_WEIGHTS),
                annual_salary_cents=_salary(rng, *department["salary_range"]),
                currency="MXN",
                hire_date=_hire_date(rng),
                phone=_phone(sequence),
            )
        )

    return profiles


RELATED_PROFILES = generate_profiles(
    count=RELATED_RECORD_COUNT,
    seed=20260608,
    sequence_start=1,
    email_namespace="shared",
    email_domain="acme.com",
)


def unique_profiles(provider: str, count: int) -> list[PersonProfile]:
    seeds = {"atlas": 11_001, "beacon": 22_002, "cobalt": 33_003}
    starts = {"atlas": 10_000, "beacon": 20_000, "cobalt": 30_000}
    return generate_profiles(
        count=count,
        seed=seeds[provider],
        sequence_start=starts[provider],
        email_namespace=provider,
        email_domain=f"{provider}.example",
    )


def _profile_groups(
    provider: str,
    seed_count: int,
) -> tuple[list[PersonProfile], list[PersonProfile]]:
    if seed_count > TARGET_RECORD_COUNT:
        raise ValueError("Seed data count cannot exceed target record count")

    unique_count = TARGET_RECORD_COUNT - seed_count - len(RELATED_PROFILES)
    if unique_count < 0:
        raise ValueError("Seed data plus related data exceeds target record count")

    return RELATED_PROFILES, unique_profiles(provider, unique_count)


def _map_profiles(
    profiles: list[PersonProfile],
    start_id: int,
    mapper: Callable[[PersonProfile, int], dict],
) -> list[dict]:
    return [
        mapper(profile, start_id + index)
        for index, profile in enumerate(profiles, start=1)
    ]


def _atlas_status(profile: PersonProfile) -> str:
    if profile.status == "FORMER":
        return "TERMINATED"
    return profile.status


def atlas_employees(seed_count: int) -> list[dict]:
    related, unique = _profile_groups("atlas", seed_count)

    def employee(profile: PersonProfile, atlas_id: int) -> dict:
        return {
            "id": f"A-{atlas_id}",
            "first_name": profile.first_name,
            "last_name": profile.last_name,
            "work_email": profile.email,
            "job_title": profile.job_title,
            "department": profile.department,
            "employment_status": _atlas_status(profile),
            "annual_salary_cents": profile.annual_salary_cents,
            "currency": profile.currency,
            "hire_date": profile.hire_date,
        }

    return _map_profiles(related, 2000, employee) + _map_profiles(unique, 5000, employee)


def _unix_ms(iso_date: str) -> int:
    dt = datetime.strptime(iso_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _monthly_amount(profile: PersonProfile) -> str:
    return f"{profile.annual_salary_cents / 100 / 12:.2f}"


def _beacon_email(profile: PersonProfile) -> str:
    if profile.sequence % 4 == 0:
        return profile.email.upper()
    if profile.sequence % 7 == 0:
        return profile.email.title()
    return profile.email


def _beacon_position(profile: PersonProfile) -> str:
    if profile.sequence % 5 == 0 and not profile.job_title.startswith("Senior"):
        return f"Senior {profile.job_title}"
    if profile.sequence % 11 == 0:
        return f"Sr. {profile.job_title}"
    return profile.job_title


def _beacon_is_active(profile: PersonProfile) -> bool:
    return profile.status != "FORMER"


def _beacon_on_leave(profile: PersonProfile) -> bool:
    return profile.status == "ON_LEAVE"


def beacon_staff(seed_count: int) -> list[dict]:
    related, unique = _profile_groups("beacon", seed_count)

    def staff_member(profile: PersonProfile, staff_id: int) -> dict:
        return {
            "staff_id": staff_id,
            "full_name": f"{profile.first_name} {profile.last_name}",
            "email": _beacon_email(profile),
            "position": _beacon_position(profile),
            "team": {"id": profile.team_id, "name": profile.department},
            "is_active": _beacon_is_active(profile),
            "on_leave": _beacon_on_leave(profile),
            "compensation": {
                "amount": _monthly_amount(profile),
                "period": "monthly",
                "currency": profile.currency,
            },
            "started_at": _unix_ms(profile.hire_date),
        }

    return _map_profiles(related, 6000, staff_member) + _map_profiles(
        unique,
        9000,
        staff_member,
    )


def _cobalt_email(profile: PersonProfile) -> str:
    if profile.sequence % 6 == 0:
        return f" {profile.email}"
    if profile.sequence % 10 == 0:
        return f"{profile.email} "
    return profile.email


def _cobalt_org_unit(profile: PersonProfile) -> str:
    for department in DEPARTMENTS:
        if department["name"] == profile.department:
            return department["cobalt_org_unit"]
    return profile.department


def _cobalt_lifecycle_status(profile: PersonProfile) -> str:
    if profile.status == "FORMER":
        return "former"
    if profile.status == "ON_LEAVE":
        return "on_leave"
    return "employed"


def _dd_mm_yyyy(iso_date: str) -> str:
    year, month, day = iso_date.split("-")
    return f"{day}/{month}/{year}"


def cobalt_people(seed_count: int) -> list[dict]:
    related, unique = _profile_groups("cobalt", seed_count)

    def person(profile: PersonProfile, offset: int) -> dict:
        return {
            "uuid": f"cobalt-{offset:04d}-{profile.sequence:x}",
            "name": {"given": profile.first_name, "family": profile.last_name},
            "contact": {"email": _cobalt_email(profile), "phone": profile.phone},
            "assignment": {
                "role": profile.job_title,
                "org_unit": _cobalt_org_unit(profile),
            },
            "lifecycle_status": _cobalt_lifecycle_status(profile),
            "pay": {
                "value": profile.annual_salary_cents // 100,
                "unit": "year",
                "iso_currency": profile.currency,
            },
            "joined": _dd_mm_yyyy(profile.hire_date),
        }

    return _map_profiles(related, 2000, person) + _map_profiles(unique, 5000, person)
