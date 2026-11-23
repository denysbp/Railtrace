import importlib
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import text

from app.db.session import SessionLocal
from app.main import app
from app.models import Batch, ReportRaw

from .conftest import RECEIVED_AT, make_line, submit, with_bad_checksum

client = TestClient(app)
process_report_module = importlib.import_module("app.services.process_report")


def outcome_row(report_id):
    with SessionLocal() as db:
        row = db.execute(text(
            "select status, quarantine_reason, raw_line, batch_id, batch_line, received_at "
            "from report_outcomes where report_raw_id = :id"
        ), {"id": report_id}).one_or_none()
    return None if row is None else tuple(row)


def store_pending(*lines, batch=False):
    """Stores reports like the API (without processing them); optionally in a batch."""
    with SessionLocal() as db:
        batch_row = Batch(name="test") if batch else None
        reports = [
            ReportRaw(raw_content=line, received_at=RECEIVED_AT, batch=batch_row, batch_line=(i + 1 if batch else None))
            for i, line in enumerate(lines)
        ]
        db.add_all(reports)
        db.commit()
        return (batch_row.id if batch else None), [r.id for r in reports]


def process(report_id):
    with SessionLocal() as db:
        process_report_module.process_report(db.get(ReportRaw, report_id), db)


# --- the Worker writes the read model ---------------------------------------------

def test_worker_writes_outcome_with_copied_fields():
    good, dup, bad = submit(make_line("SPD=20"), make_line("SPD=20.0"), with_bad_checksum(make_line("SPD=1")))
    assert outcome_row(good)[:2] == ("applied", None)
    assert outcome_row(dup)[:2] == ("duplicate", None)
    status, reason, raw_line, batch_id, batch_line, received_at = outcome_row(bad)
    assert (status, reason, batch_id, batch_line) == ("quarantined", "bad_checksum", None, None)
    assert raw_line == with_bad_checksum(make_line("SPD=1"))
    assert received_at == RECEIVED_AT


def test_conflict_updates_outcome_of_already_applied_report():
    (first,) = submit(make_line("SPD=20"))
    assert outcome_row(first)[:2] == ("applied", None)
    (second,) = submit(make_line("SPD=25"))
    assert outcome_row(first)[:2] == ("quarantined", "conflict")
    assert outcome_row(second)[:2] == ("quarantined", "conflict")


def test_technical_error_writes_no_outcome(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(process_report_module, "_rebuild_measurement", boom)
    (report,) = submit(make_line("SPD=20"))
    assert outcome_row(report) is None  # remains pending: no outcome


def test_unprocessed_reports_have_no_outcome_and_count_as_pending():
    batch_id, (a, b, c) = store_pending(make_line("SPD=1", measured_at="2026-11-02T08:00:00Z"),
                                        make_line("SPD=2", measured_at="2026-11-02T08:05:00Z"),
                                        with_bad_checksum(make_line("SPD=3")), batch=True)
    process(a)
    process(c)
    assert outcome_row(b) is None
    assert client.get(f"/v1/depot/batches/{batch_id}").json() == {
        "batch_id": batch_id, "lines": 3, "applied": 1, "duplicate": 0, "pending": 1,
        "quarantined": {"bad_checksum": 1},
    }
    stats = client.get("/v1/stats").json()
    assert (stats["reports_total"], stats["pending"]) == (3, 1)


# --- the endpoints read the read model, not reports_raw ------------------------------

def test_endpoints_read_report_outcomes_not_reports_raw():
    batch_id, (report,) = store_pending(with_bad_checksum(make_line("SPD=1")), batch=True)
    process(report)
    # Only touches reports_raw (the read model stays the same): the responses must not change
    with SessionLocal() as db:
        db.execute(text("update reports_raw set status = 'applied', quarantine_reason = null where id = :id"), {"id": report})
        db.commit()

    assert client.get(f"/v1/depot/batches/{batch_id}").json()["quarantined"] == {"bad_checksum": 1}
    assert client.get("/v1/stats").json()["quarantined"] == {"bad_checksum": 1}
    listed = client.get("/v1/quarantine", params={"reason": "bad_checksum", "limit": 10}).json()
    assert listed == [{
        "reason": "bad_checksum",
        "raw_line": with_bad_checksum(make_line("SPD=1")),
        "source": f"batch:{batch_id}:line:1",
        "received_at": RECEIVED_AT.isoformat().replace("+00:00", "Z"),
    }]


def test_quarantine_lists_most_recent_first_and_respects_limit():
    late = datetime(2026, 11, 4, tzinfo=timezone.utc)
    (older,) = submit(make_line("SPD=1", serial="TS-0099", measured_at="2026-11-02T08:00:00Z"))
    (newer,) = submit(make_line("SPD=2", serial="TS-0099", measured_at="2026-11-02T08:05:00Z"), received_at=late)
    listed = client.get("/v1/quarantine", params={"reason": "unknown_trainset", "limit": 10}).json()
    assert [item["source"] for item in listed] == ["live", "live"]
    assert [item["received_at"] for item in listed] == ["2026-11-04T00:00:00Z", "2026-11-03T00:00:00Z"]
    assert len(client.get("/v1/quarantine", params={"reason": "unknown_trainset", "limit": 1}).json()) == 1
    assert client.get("/v1/quarantine", params={"reason": "malformed", "limit": 10}).json() == []
