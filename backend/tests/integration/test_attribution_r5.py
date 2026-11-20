"""R5: atribuição das medições às duties, no worker e quando um assignment é criado/alterado.

Seed, TS-0001 em 2026-11-02: AZ-D01-20261102 [07:00, 11:00) e AZ-D02-20261102 [13:00, 17:00).
"""

from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.main import app
from app.models import Assignment, Duty

from .conftest import make_line, submit

DAY = "2026-11-02"
client = TestClient(app)


def at(hhmm):
    return f"{DAY}T{hhmm}:00Z"


def duty_of(hhmm):
    """Código da duty da medição da TS-0001 nesse instante (None = não atribuída)."""
    with SessionLocal() as db:
        return db.scalar(text(
            "select d.code from measurements m join trainsets t on t.id = m.trainset_id "
            "left join duties d on d.id = m.duty_id "
            "where t.serial = 'TS-0001' and m.measured_at = :at"
        ), {"at": datetime.fromisoformat(at(hhmm))})


def measurements_at(*times):
    submit(*(make_line("SPD=10", measured_at=at(hhmm)) for hhmm in times))


def seed_assignment_id(duty_code):
    with SessionLocal() as db:
        return db.scalar(select(Assignment.id).join(Duty).where(Duty.code == duty_code))


# --- worker ------------------------------------------------------------------

@pytest.mark.parametrize("hhmm, expected", [
    ("07:00", "AZ-D01-20261102"),  # início incluído
    ("10:55", "AZ-D01-20261102"),
    ("11:00", None),               # fim excluído
    ("12:00", None),               # entre duties
    ("13:00", "AZ-D02-20261102"),
])
def test_worker_attributes_measurement_to_covering_assignment(hhmm, expected):
    measurements_at(hhmm)
    assert duty_of(hhmm) == expected


# --- criação de assignment -----------------------------------------------------

def test_creating_assignment_attributes_existing_measurements():
    measurements_at("11:30", "12:00", "13:00", "08:00")
    assert duty_of("11:30") is None and duty_of("12:00") is None

    response = client.post(
        "/v1/duties/AZ-D01-20261102/assignments",
        json={"trainset": "TS-0001", "started_at": at("11:00"), "ended_at": at("13:00")},
    )
    assert response.status_code == 201
    assert duty_of("11:30") == "AZ-D01-20261102"
    assert duty_of("12:00") == "AZ-D01-20261102"
    assert duty_of("13:00") == "AZ-D02-20261102"  # fora do novo intervalo: não muda
    assert duty_of("08:00") == "AZ-D01-20261102"


# --- alteração de assignment -----------------------------------------------------

def test_shrinking_assignment_unattributes_measurements_that_leave_it():
    measurements_at("08:00", "09:30", "10:00")
    response = client.patch(f"/v1/assignments/{seed_assignment_id('AZ-D01-20261102')}", json={"ended_at": at("09:00")})
    assert response.status_code == 200
    assert duty_of("08:00") == "AZ-D01-20261102"
    assert duty_of("09:30") is None
    assert duty_of("10:00") is None


def test_extending_assignment_attributes_measurements_that_enter_it():
    measurements_at("06:30")
    assert duty_of("06:30") is None
    response = client.patch(f"/v1/assignments/{seed_assignment_id('AZ-D01-20261102')}", json={"started_at": at("06:00")})
    assert response.status_code == 200
    assert duty_of("06:30") == "AZ-D01-20261102"


def test_overlapping_change_is_409_and_keeps_attribution():
    measurements_at("10:00", "12:00")
    # estender AZ-D01 até às 14:00 sobrepõe AZ-D02 (mesma composição)
    response = client.patch(f"/v1/assignments/{seed_assignment_id('AZ-D01-20261102')}", json={"ended_at": at("14:00")})
    assert response.status_code == 409
    assert duty_of("10:00") == "AZ-D01-20261102"
    assert duty_of("12:00") is None
