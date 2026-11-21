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
        pytest.exit(f"Os testes de integração só correm na railtrace-test (não em {engine.url.database})")
    try:
        with SessionLocal() as db:
            load_seed(db, SEED_FILE)  # idempotente
    except OperationalError as e:
        pytest.skip(f"BD de testes indisponível: {e.orig}")


@pytest.fixture(autouse=True)
def clean_tables():
    """Cada teste começa sem relatórios, revisões nem medições, e com os assignments do seed
    (há testes que os criam ou alteram)."""
    with engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE measurement_metrics, measurements, report_revision_metrics, "
            "report_revisions, reports_raw, batches, assignments, "
            "duty_hourly_rollups, duty_metric_summaries, duty_station_stats RESTART IDENTITY CASCADE"
        ))
    with engine.begin() as conn:
        # composições registadas pelos testes (ex.: R8); as do seed ficam
        seed_serials = [t["serial"] for t in json.loads(SEED_FILE.read_text())["trainsets"]]
        conn.execute(text("DELETE FROM trainsets WHERE serial <> ALL(:serials)"), {"serials": seed_serials})
    with SessionLocal() as db:
        load_seed(db, SEED_FILE)  # repõe os assignments


def make_line(metrics, *, rev=0, station="SSE", serial="TS-0001", measured_at=MEASURED_AT):
    """Relatório $TRN com checksum correto."""
    body = f"TRN,{serial},{measured_at},{rev},{station},{metrics}"
    checksum = 0
    for byte in body.encode():
        checksum ^= byte
    return f"${body}*{checksum:02X}"


def with_bad_checksum(line):
    """O mesmo relatório com um checksum de 2 dígitos errado."""
    return line[:-2] + ("00" if line[-2:] != "00" else "01")


def submit(*lines, received_at=RECEIVED_AT):
    """Grava os relatórios (como a API) e processa-os por ordem (como o Worker).

    Devolve os ids dos relatórios.
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
    """(status, quarantine_reason) de um relatório, como texto."""
    with SessionLocal() as db:
        report = db.get(ReportRaw, report_id)
        reason = report.quarantine_reason.value if report.quarantine_reason else None
        return report.status.value, reason


def measurement(serial="TS-0001", measured_at=MEASURED_AT):
    """Estado da medição: (código da estação, {métrica: valor}) ou None se não aparece."""
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
