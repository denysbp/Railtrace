"""Worker: a technical error leaves the report pending and it is tried again on the
next pass through the queue, without restarting and without consecutive attempts."""

import contextlib
import importlib
import io

import pytest

import app.worker as worker_module
from app.db.session import SessionLocal
from app.models import ReportRaw

from .conftest import RECEIVED_AT, make_line, outcome

process_report_module = importlib.import_module("app.services.process_report")


class StopWorker(Exception):
    pass


def store(*lines):
    """Stores pending reports, like the API (without processing them)."""
    with SessionLocal() as db:
        reports = [ReportRaw(raw_content=line, received_at=RECEIVED_AT) for line in lines]
        db.add_all(reports)
        db.commit()
        return [report.id for report in reports]


def run_worker(monkeypatch, passes):
    """Runs the Worker until `passes` passes through the queue (each end of queue = one sleep)."""
    sleeps = {"n": 0}

    def fake_sleep(_):
        sleeps["n"] += 1
        if sleeps["n"] >= passes:
            raise StopWorker

    monkeypatch.setattr(worker_module, "sleep", fake_sleep)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        with pytest.raises(StopWorker):
            worker_module.Worker().run()


def fail_for(monkeypatch, failing_ids, times=None):
    """Makes _apply_revision fail for the reports in `failing_ids`.

    times=None: always fails. Returns the list of attempted ids, in order.
    """
    original = process_report_module._apply_revision
    attempts = []
    failures = {"n": 0}

    def flaky(report, *args, **kwargs):
        attempts.append(report.id)
        if report.id in failing_ids and (times is None or failures["n"] < times):
            failures["n"] += 1
            raise RuntimeError("simulated technical failure")
        return original(report, *args, **kwargs)

    monkeypatch.setattr(process_report_module, "_apply_revision", flaky)
    return attempts


def test_temporary_failure_is_retried_in_the_next_pass_without_restart(monkeypatch):
    (report,) = store(make_line("SPD=20"))
    attempts = fail_for(monkeypatch, {report}, times=1)

    run_worker(monkeypatch, passes=3)

    assert attempts == [report, report]  # 1st pass fails, 2nd applies
    assert outcome(report) == ("applied", None)


def test_permanent_failure_does_not_block_others_and_is_tried_once_per_pass(monkeypatch):
    broken, ok = store(make_line("SPD=20", measured_at="2026-11-02T08:00:00Z"),
                       make_line("SPD=30", measured_at="2026-11-02T08:05:00Z"))
    attempts = fail_for(monkeypatch, {broken})

    run_worker(monkeypatch, passes=4)

    assert outcome(ok) == ("applied", None)        # was not blocked by the one that fails
    assert outcome(broken) == ("pending", None)    # remains pending for a new attempt
    assert attempts.count(broken) == 4             # one attempt per pass
    assert attempts.count(ok) == 1


def test_no_immediate_retry_of_the_same_report(monkeypatch):
    (report,) = store(make_line("SPD=20"))
    attempts = fail_for(monkeypatch, {report})
    sleeps_between = []

    def recording_sleep(_):
        sleeps_between.append(len(attempts))
        if len(sleeps_between) >= 3:
            raise StopWorker

    monkeypatch.setattr(worker_module, "sleep", recording_sleep)
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        with pytest.raises(StopWorker):
            worker_module.Worker().run()

    # after each failed attempt there is a sleep before the next one
    assert sleeps_between == [1, 2, 3]
