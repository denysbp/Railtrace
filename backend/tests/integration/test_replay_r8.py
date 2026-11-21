from sqlalchemy import select, text

from app.cli import main
from app.db.session import SessionLocal
from app.models import Line, QuarantineReason, Trainset
from app.services.replay import replay_quarantine

from .conftest import make_line, measurement, outcome, revisions_count, submit, with_bad_checksum

UNKNOWN = ("quarantined", "unknown_trainset")


def register_trainset(serial, line_code="AZ"):
    with SessionLocal() as db:
        line_id = db.scalar(select(Line.id).where(Line.code == line_code))
        db.add(Trainset(serial=serial, home_line_id=line_id))
        db.commit()


def outcome_row(report_id):
    with SessionLocal() as db:
        return db.execute(text("select status, quarantine_reason from report_outcomes where report_raw_id = :id"),
                          {"id": report_id}).one()


def test_replay_applies_report_after_trainset_is_registered():
    (report,) = submit(make_line("SPD=20", serial="TS-0099"))
    assert outcome(report) == UNKNOWN

    register_trainset("TS-0099")
    results = replay_quarantine(QuarantineReason.UNKNOWN_TRAINSET)

    assert [(r.report_id, r.status.value, r.reason, r.changed) for r in results] == [(report, "applied", None, True)]
    assert outcome(report) == ("applied", None)
    assert outcome_row(report) == ("applied", None)  # read model atualizado
    assert measurement(serial="TS-0099") is not None


def test_dry_run_only_prints_and_changes_nothing():
    first, second = submit(make_line("SPD=20", serial="TS-0099"), make_line("SPD=20.0", serial="TS-0099"))
    register_trainset("TS-0099")

    preview = replay_quarantine(QuarantineReason.UNKNOWN_TRAINSET, dry_run=True)
    # vê o efeito do primeiro no segundo: aplicado + duplicado, como na execução real
    assert [r.status.value for r in preview] == ["applied", "duplicate"]
    assert outcome(first) == UNKNOWN and outcome(second) == UNKNOWN
    assert outcome_row(first) == ("quarantined", "unknown_trainset")
    assert revisions_count() == 0
    assert measurement(serial="TS-0099") is None

    real = replay_quarantine(QuarantineReason.UNKNOWN_TRAINSET)
    assert [(r.report_id, r.status, r.reason) for r in real] == [(r.report_id, r.status, r.reason) for r in preview]


def test_replay_keeps_reports_that_still_fail():
    (bad,) = submit(with_bad_checksum(make_line("SPD=1")))
    (unknown,) = submit(make_line("SPD=1", serial="TS-0099"))  # composição continua por registar

    assert [r.changed for r in replay_quarantine(QuarantineReason.BAD_CHECKSUM)] == [False]
    assert [r.changed for r in replay_quarantine(QuarantineReason.UNKNOWN_TRAINSET)] == [False]
    assert outcome(bad) == ("quarantined", "bad_checksum")
    assert outcome(unknown) == UNKNOWN


def test_replay_only_touches_the_chosen_reason():
    (unknown_station,) = submit(make_line("SPD=1", station="XPO"))
    (unknown_trainset,) = submit(make_line("SPD=1", serial="TS-0099"))
    register_trainset("TS-0099")

    results = replay_quarantine(QuarantineReason.UNKNOWN_TRAINSET)
    assert [r.report_id for r in results] == [unknown_trainset]
    assert outcome(unknown_station) == ("quarantined", "unknown_station")


def test_replaying_a_conflict_keeps_it_in_conflict():
    first, second = submit(make_line("SPD=20"), make_line("SPD=25"))
    revisions_before = revisions_count()

    results = replay_quarantine(QuarantineReason.CONFLICT)
    assert [r.changed for r in results] == [False, False]
    assert outcome(first) == outcome(second) == ("quarantined", "conflict")
    assert revisions_count() == revisions_before  # a revisão já guardada não é duplicada
    assert measurement() is None


def test_cli_replay_quarantine(capsys):
    (report,) = submit(make_line("SPD=20", serial="TS-0099"))
    register_trainset("TS-0099")

    main(["replay-quarantine", "--reason", "unknown_trainset", "--dry-run"])
    out = capsys.readouterr().out
    assert f"[dry-run] report {report}: unknown_trainset -> applied" in out
    assert "1 report(s) checked, 1 would change" in out
    assert outcome(report) == UNKNOWN

    main(["replay-quarantine", "--reason", "unknown_trainset"])
    assert "1 changed" in capsys.readouterr().out
    assert outcome(report) == ("applied", None)
