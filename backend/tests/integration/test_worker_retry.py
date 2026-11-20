"""Worker: um erro técnico deixa o relatório pending e ele é tentado outra vez na
passagem seguinte pela fila, sem reiniciar e sem tentativas seguidas."""

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
    """Grava relatórios pending, como a API (sem os processar)."""
    with SessionLocal() as db:
        reports = [ReportRaw(raw_content=line, received_at=RECEIVED_AT) for line in lines]
        db.add_all(reports)
        db.commit()
        return [report.id for report in reports]


def run_worker(monkeypatch, passes):
    """Corre o Worker até `passes` passagens pela fila (cada fim de fila = um sleep)."""
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
    """Faz _apply_revision falhar para os relatórios em `failing_ids`.

    times=None: falha sempre. Devolve a lista de ids tentados, por ordem.
    """
    original = process_report_module._apply_revision
    attempts = []
    failures = {"n": 0}

    def flaky(report, *args, **kwargs):
        attempts.append(report.id)
        if report.id in failing_ids and (times is None or failures["n"] < times):
            failures["n"] += 1
            raise RuntimeError("falha técnica simulada")
        return original(report, *args, **kwargs)

    monkeypatch.setattr(process_report_module, "_apply_revision", flaky)
    return attempts


def test_temporary_failure_is_retried_in_the_next_pass_without_restart(monkeypatch):
    (report,) = store(make_line("SPD=20"))
    attempts = fail_for(monkeypatch, {report}, times=1)

    run_worker(monkeypatch, passes=3)

    assert attempts == [report, report]  # 1ª passagem falha, 2ª aplica
    assert outcome(report) == ("applied", None)


def test_permanent_failure_does_not_block_others_and_is_tried_once_per_pass(monkeypatch):
    broken, ok = store(make_line("SPD=20", measured_at="2026-11-02T08:00:00Z"),
                       make_line("SPD=30", measured_at="2026-11-02T08:05:00Z"))
    attempts = fail_for(monkeypatch, {broken})

    run_worker(monkeypatch, passes=4)

    assert outcome(ok) == ("applied", None)        # não ficou bloqueado pelo que falha
    assert outcome(broken) == ("pending", None)    # continua pending para nova tentativa
    assert attempts.count(broken) == 4             # uma tentativa por passagem
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

    # depois de cada tentativa falhada há um sleep antes da seguinte
    assert sleeps_between == [1, 2, 3]
