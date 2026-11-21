import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.cli import main
from app.db.session import SessionLocal
from app.main import app
from app.models import Assignment, Batch, Duty, Line, QuarantineReason, ReportRaw, Trainset
from app.services.rebuild import rebuild_read_models
from app.services.replay import replay_quarantine

from .conftest import RECEIVED_AT, make_line, submit, with_bad_checksum

client = TestClient(app)
rebuild_module = importlib.import_module("app.services.rebuild")
AZ1 = "AZ-D01-20261102"


def at(hhmm):
    return f"2026-11-02T{hhmm}:00Z"


def build_history():
    """Um pouco de tudo: aplicados, duplicado, revisões, remoção, conflito com recuo,
    quarentenas, um batch e uma alteração de assignment."""
    submit(
        make_line("SPD=10;KWH=1;AX1=36", measured_at=at("07:00"), station="REB"),
        make_line("SPD=10.00;KWH=1;AX1=36", measured_at=at("07:00"), station="REB"),       # duplicado
        make_line("SPD=20;AX1=38", measured_at=at("07:05"), rev=0, station="ALF"),
        make_line("SPD=22;AX1=-", measured_at=at("07:05"), rev=1, station="ALF"),          # revisão + remoção
        make_line("SPD=30", measured_at=at("08:00"), rev=0),
        make_line("SPD=31", measured_at=at("08:00"), rev=1),
        make_line("SPD=99", measured_at=at("08:00"), rev=1),                               # conflito -> recua a rev 0
        make_line("SPD=40", measured_at=at("12:00")),                                      # não atribuída
        with_bad_checksum(make_line("SPD=1", measured_at=at("09:00"))),
        make_line("SPD=1", measured_at=at("09:05"), serial="TS-0099"),
    )
    with SessionLocal() as db:  # batch gravado como a API
        batch = Batch(name="teste")
        db.add_all([
            ReportRaw(raw_content=make_line("SPD=50", measured_at=at("09:30")), received_at=RECEIVED_AT, batch=batch, batch_line=1),
            ReportRaw(raw_content=make_line("SPD=10;KWH=1;AX1=36", measured_at=at("07:00"), station="REB"),
                      received_at=RECEIVED_AT, batch=batch, batch_line=2),                 # duplicado vindo do batch
        ])
        db.commit()
        batch_id = batch.id
        pending = db.scalars(select(ReportRaw).where(ReportRaw.batch_id == batch_id).order_by(ReportRaw.id)).all()
    from app.services import process_report
    for report in pending:
        with SessionLocal() as db:
            process_report(db.get(ReportRaw, report.id), db)
    assignment_id = None
    with SessionLocal() as db:
        assignment_id = db.scalar(select(Assignment.id).join(Duty).where(Duty.code == AZ1))
    assert client.patch(f"/v1/assignments/{assignment_id}", json={"ended_at": at("09:00")}).status_code == 200
    return batch_id


def api_answers(batch_id):
    """Todas as respostas da API que dependem dos read models."""
    answers = {
        "stats": client.get("/v1/stats").json(),
        "batch": client.get(f"/v1/depot/batches/{batch_id}").json(),
        "quarantine": {r.value: client.get("/v1/quarantine", params={"reason": r.value, "limit": 100}).json() for r in QuarantineReason},
    }
    for duty in (AZ1, "AZ-D02-20261102"):
        answers[duty] = {
            "summary": client.get(f"/v1/duties/{duty}/summary").json(),
            "stations": client.get(f"/v1/duties/{duty}/stations").json(),
            **{f"hourly_{m}": client.get(f"/v1/duties/{duty}/hourly", params={"metric": m}).json() for m in ("SPD", "KWH", "AX1")},
            **{f"readings_{m}": client.get(f"/v1/duties/{duty}/readings", params={"metric": m}).json() for m in ("SPD", "KWH", "AX1")},
        }
    return answers


def test_rebuild_gives_the_same_api_answers():
    batch_id = build_history()
    before = api_answers(batch_id)
    assert before["stats"]["measurements"] > 0 and before["stats"]["quarantined"]  # o histórico tem conteúdo

    with SessionLocal() as db:
        counts = rebuild_read_models(db)
    assert counts["reports"] == before["stats"]["reports_total"]
    assert api_answers(batch_id) == before


def test_rebuild_repairs_damaged_read_models():
    batch_id = build_history()
    before = api_answers(batch_id)
    with SessionLocal() as db:  # estraga os read models
        db.execute(text("delete from duty_hourly_rollups; delete from report_outcomes; delete from measurements"))
        db.commit()
    assert api_answers(batch_id) != before

    with SessionLocal() as db:
        rebuild_read_models(db)
    assert api_answers(batch_id) == before


def test_rebuild_failure_changes_nothing(monkeypatch):
    batch_id = build_history()
    before = api_answers(batch_id)
    calls = {"n": 0}
    original = rebuild_module.apply_rules

    def fail_on_fifth(report, db):
        calls["n"] += 1
        if calls["n"] == 5:
            raise RuntimeError("falha a meio do rebuild")
        return original(report, db)

    monkeypatch.setattr(rebuild_module, "apply_rules", fail_on_fifth)
    with SessionLocal() as db, pytest.raises(RuntimeError):
        rebuild_read_models(db)
    assert api_answers(batch_id) == before  # tudo numa transação: nada mudou


def test_rebuild_keeps_reports_fixed_by_replay():
    (report,) = submit(make_line("SPD=7", measured_at=at("10:00"), serial="TS-0099"))
    with SessionLocal() as db:
        db.add(Trainset(serial="TS-0099", home_line_id=db.scalar(select(Line.id).where(Line.code == "AZ"))))
        db.commit()
    replay_quarantine(QuarantineReason.UNKNOWN_TRAINSET)
    before = client.get("/v1/stats").json()
    assert before["quarantined"] == {}

    with SessionLocal() as db:
        rebuild_read_models(db)
    assert client.get("/v1/stats").json() == before


def test_cli_rebuild_read_models(capsys):
    submit(make_line("SPD=10", measured_at=at("07:00")), with_bad_checksum(make_line("SPD=1", measured_at=at("07:05"))))
    main(["rebuild-read-models"])
    assert capsys.readouterr().out.strip() == "rebuilt read models from 2 report(s): 1 measurement(s)"
