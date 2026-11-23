import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import OperationalError

from app.db.session import SessionLocal, engine
from app.models import Measurement, ReportRaw, Trainset
from app.services import process_report
from app.services.seed import load_seed

SEED_FILE = Path(__file__).resolve().parents[3] / "data" / "seed.json"
RECEIVED_AT = datetime(2026, 11, 3, 0, 0, tzinfo=timezone.utc)
MEASURED_AT = "2026-11-02T08:00:00Z"


@pytest.fixture(scope="session", autouse=True)
def test_database():
    if engine.url.database != "railtrace-test":
        pytest.exit(f"Integration tests only run on railtrace-test (not on {engine.url.database})")
    try:
        with SessionLocal() as db:
            load_seed(db, SEED_FILE)  # idempotent
    except OperationalError as e:
        pytest.skip(f"Test DB unavailable: {e.orig}")


@pytest.fixture(autouse=True)
def clean_tables():
    """Each test starts with no reports, revisions, or measurements, and with the seed assignments
    (some tests create or change them)."""
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE measurement_metrics, measurements, report_revision_metrics, "
            "report_revisions, reports_raw, batches, assignments, "
            "duty_hourly_rollups, duty_metric_summaries, duty_station_stats RESTART IDENTITY CASCADE"
        ))
    with engine.begin() as conn:
        # trainsets registered by tests (e.g. R8); the seed ones remain
        seed_serials = [t["serial"] for t in json.loads(SEED_FILE.read_text())["trainsets"]]
        conn.execute(text("DELETE FROM trainsets WHERE serial <> ALL(:serials)"), {"serials": seed_serials})
    with SessionLocal() as db:
        load_seed(db, SEED_FILE)  # restores the assignments


def make_line(metrics, *, rev=0, station="SSE", serial="TS-0001", measured_at=MEASURED_AT):
    """$TRN report with a correct checksum."""
    body = f"TRN,{serial},{measured_at},{rev},{station},{metrics}"
    checksum = 0
    for byte in body.encode():
        checksum ^= byte
    return f"${body}*{checksum:02X}"


def with_bad_checksum(line):
    """The same report with an incorrect 2-digit checksum."""
    return line[:-2] + ("00" if line[-2:] != "00" else "01")


def submit(*lines, received_at=RECEIVED_AT):
    """Stores the reports (like the API) and processes them in order (like the Worker).

    Returns the ids of the reports.
    """
    ids = []
    for line in lines:
        with SessionLocal() as db:
            report = ReportRaw(raw_content=line, received_at=received_at)
            db.add(report)
            db.commit()
            ids.append(report.id)
        with SessionLocal() as db:
            process_report(db.get(ReportRaw, ids[-1]), db)
    return ids


def outcome(report_id):
    """(status, quarantine_reason) of a report, as text."""
    with SessionLocal() as db:
        report = db.get(ReportRaw, report_id)
        reason = report.quarantine_reason.value if report.quarantine_reason else None
        return report.status.value, reason


def measurement(serial="TS-0001", measured_at=MEASURED_AT):
    """Measurement state: (station code, {metric: value}) or None if it does not appear."""
    with SessionLocal() as db:
        row = db.scalar(
            select(Measurement)
            .join(Trainset, Trainset.id == Measurement.trainset_id)
            .where(Trainset.serial == serial, Measurement.measured_at == datetime.fromisoformat(measured_at))
        )
        if row is None:
            return None
        station = db.scalar(text("select code from stations where id = :i"), {"i": row.station_id}) if row.station_id else None
        return station, {m.metric: m.value for m in row.metrics}


def revisions_count():
    with SessionLocal() as db:
        return db.scalar(text("select count(*) from report_revisions"))
