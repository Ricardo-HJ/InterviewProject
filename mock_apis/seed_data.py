"""Small hand-written records that document each provider's shape quirks."""

from __future__ import annotations

from datetime import datetime, timezone


def _unix_ms(iso_date: str) -> int:
    dt = datetime.strptime(iso_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


ATLAS_EMPLOYEES: list[dict] = [
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


BEACON_STAFF: list[dict] = [
    {
        "staff_id": 5001,
        "full_name": "Maria Gonzalez",
        "email": "MARIA.GONZALEZ@acme.com",
        "position": "Sr. Software Engineer",
        "team": {"id": 12, "name": "Engineering"},
        "is_active": True,
        "on_leave": False,
        "compensation": {"amount": "70000.00", "period": "monthly", "currency": "MXN"},
        "started_at": _unix_ms("2021-03-15"),
    },
    {
        "staff_id": 5002,
        "full_name": "Yuki Tanaka",
        "email": "yuki.tanaka@acme.com",
        "position": "Data Analyst",
        "team": {"id": 8, "name": "Data"},
        "is_active": True,
        "on_leave": True,
        "compensation": {"amount": "60000.00", "period": "monthly", "currency": "MXN"},
        "started_at": _unix_ms("2022-01-10"),
    },
    {
        "staff_id": 5003,
        "full_name": "Aisha Khan",
        "email": "Aisha.Khan@ACME.com",
        "position": "Senior Designer",
        "team": {"id": 5, "name": "Design"},
        "is_active": True,
        "on_leave": False,
        "compensation": {"amount": "65000.00", "period": "monthly", "currency": "MXN"},
        "started_at": _unix_ms("2020-11-23"),
    },
    {
        "staff_id": 5004,
        "full_name": "Liang Wei",
        "email": "liang.wei@acme.com",
        "position": "Backend Engineer",
        "team": {"id": 12, "name": "Engineering"},
        "is_active": True,
        "on_leave": False,
        "compensation": {"amount": "72500.00", "period": "monthly", "currency": "MXN"},
        "started_at": _unix_ms("2021-09-30"),
    },
    {
        "staff_id": 5005,
        "full_name": "Sofia Rossi",
        "email": "sofia.rossi@acme.com",
        "position": "Marketing Lead",
        "team": {"id": 3, "name": "Marketing"},
        "is_active": True,
        "on_leave": False,
        "compensation": {"amount": "67500.00", "period": "monthly", "currency": "MXN"},
        "started_at": _unix_ms("2017-03-19"),
    },
]


COBALT_PEOPLE: list[dict] = [
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
        "assignment": {
            "role": "Customer Success Manager",
            "org_unit": "Customer Success",
        },
        "lifecycle_status": "former",
        "pay": {"value": 750000, "unit": "year", "iso_currency": "MXN"},
        "joined": "22/08/2016",
    },
]
