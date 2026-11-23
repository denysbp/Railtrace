import traceback
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload
from app.models import (
    Measurement,
    MeasurementMetric,
    ReportOutcome,
    ReportRaw,
    ReportRevision,
    ReportRevisionMetric,
    Station,
    Trainset,
)
from app.domain import (
    Revision,
    RevisionContent,
    RevisionOutcome,
    apply_revisions,
    check_sum_valid,
    classify_revision,
    find_duty,
    has_unknown_metric,
    is_clock_invalid,
    is_malformated_fields,
    is_malformated_form,
    parse_report,
)
from app.models import ReportStatus, QuarantineReason
from app.services.attribution import assignment_periods
from app.services.locks import lock_read_models_shared
from app.services.rollups import refresh_rollups


def _set_outcome(
    db: Session,
    report: ReportRaw,
    status: ReportStatus,
    reason: QuarantineReason | None = None,
) -> None:
    """Stores the result of a report: the status in reports_raw (removes it from the queue)
    and the report_outcomes read model (what the endpoints read, A2).

    No commit: the commit is done once at the end of process_report (A3).
    Upsert because R4 can change an already processed report to conflict.
    """
    report.status = status
    report.quarantine_reason = reason
    values = {
        "report_raw_id": report.id,
        "batch_id": report.batch_id,
        "batch_line": report.batch_line,
        "status": status,
        "quarantine_reason": reason,
        "raw_line": report.raw_content,
        "received_at": report.received_at,
    }
    db.execute(
        insert(ReportOutcome)
        .values(values)
        .on_conflict_do_update(
            index_elements=[ReportOutcome.report_raw_id],
            set_={"status": status, "quarantine_reason": reason},
        )
    )


def _quarantine(
    db: Session,
    report: ReportRaw,
    reason: QuarantineReason,
) -> None:
    _set_outcome(db, report, ReportStatus.QUARANTINED, reason)


def process_report(report: ReportRaw, db: Session) -> bool:
    """Applies the rules to a report in a single transaction.

    Returns False on a technical error: rolls back and the report stays
    pending, to be tried again.
    """
    try:
        lock_read_models_shared(db)  # waits if a rebuild (A4) is running
        apply_rules(report, db)
        db.commit()
        return True
    except Exception:
        db.rollback()
        traceback.print_exc()  # do not hide the error
        return False


def apply_rules(report: ReportRaw, db: Session) -> None:
    """Applies R1–R5 and R7 to a report, without commit (the caller manages the transaction).

    R1: checks in challenge order; the first one that fails gives the reason.
    """
    text = report.raw_content
    # 1. Form $...*hh, with no other $ or *
    if is_malformated_form(text):
        _quarantine(db, report, QuarantineReason.MALFORMED)
        return
    # 2. Checksum
    if not check_sum_valid(text):
        _quarantine(db, report, QuarantineReason.BAD_CHECKSUM)
        return
    # 3. 6 fields, type TRN, each field valid, no repeated keys, ≥ 1 metric
    if is_malformated_fields(text):
        _quarantine(db, report, QuarantineReason.MALFORMED)
        return
    parsed = parse_report(text)
    # 4. All metric keys are known
    if has_unknown_metric(text[1:].split("*")[0].split(",")[5]):
        _quarantine(db, report, QuarantineReason.UNKNOWN_METRIC)
        return
    # 5. Station "-" or known (None = "-")
    station_id = None
    if parsed.station is not None:
        station_id = db.scalar(select(Station.id).where(Station.code == parsed.station))
        if station_id is None:
            _quarantine(db, report, QuarantineReason.UNKNOWN_STATION)
            return
    # 6. Trainset registered
    trainset_id = db.scalar(select(Trainset.id).where(Trainset.serial == parsed.serial))
    if trainset_id is None:
        _quarantine(db, report, QuarantineReason.UNKNOWN_TRAINSET)
        return
    # 7. Clock: received_at = when the API stored the report, not when the Worker processes it
    if is_clock_invalid(parsed.measured_at, report.received_at):
        _quarantine(db, report, QuarantineReason.CLOCK_INVALID)
        return
    # 8. Conflict (R4), inside _apply_revision
    measured_at = datetime.fromisoformat(parsed.measured_at)  # valid: passed is_clock_invalid
    _apply_revision(report, db, trainset_id, measured_at, parsed.rev, station_id, parsed.metrics)


def _apply_revision(report, db, trainset_id, measured_at, rev, station_id, metrics) -> None:
    """R2 + R4: compares with revisions already stored with the same identity."""
    # Revisions with the same identity (serial, measured_at, rev) and the status of their reports
    existing = db.scalars(
        select(ReportRevision)
        .where(
            ReportRevision.trainset_id == trainset_id,
            ReportRevision.measured_at == measured_at,
            ReportRevision.rev == rev,
        )
        .options(selectinload(ReportRevision.metrics), selectinload(ReportRevision.report_raw))
    ).all()
    # In a replay (R8) the report may already have its revision: it does not count as "other"
    already_stored = any(other.report_raw_id == report.id for other in existing)
    existing = [other for other in existing if other.report_raw_id != report.id]
    identity_in_conflict = any(
        other.report_raw.quarantine_reason == QuarantineReason.CONFLICT for other in existing
    )
    new_content = RevisionContent(station=station_id, metrics=metrics)
    outcome = classify_revision(
        new_content,
        [_content(other) for other in existing],
        identity_in_conflict,
    )

    # Always store the revision (also duplicates and conflicts): it is the record of
    # this report's identity, needed so a later conflict can find it (R4).
    if not already_stored:
        db.add(
            ReportRevision(
                report_raw_id=report.id,
                trainset_id=trainset_id,
                measured_at=measured_at,
                rev=rev,
                station_id=station_id,
                metrics=[ReportRevisionMetric(metric=name, value=value) for name, value in metrics.items()],
            )
        )

    if outcome is RevisionOutcome.DUPLICATE:
        _set_outcome(db, report, ReportStatus.DUPLICATE)  # does not change the measurement (R2)
        return

    if outcome is RevisionOutcome.NEW:
        _set_outcome(db, report, ReportStatus.APPLIED)
    else:
        # R4: all reports with this identity become conflict, including the applied ones
        _quarantine(db, report, QuarantineReason.CONFLICT)
        for other in existing:
            _quarantine(db, other.report_raw, QuarantineReason.CONFLICT)

    db.flush()
    _rebuild_measurement(db, trainset_id, measured_at)


def _content(revision: ReportRevision) -> RevisionContent:
    return RevisionContent(
        station=revision.station_id,
        metrics={metric.metric: metric.value for metric in revision.metrics},
    )


def _rebuild_measurement(db: Session, trainset_id: int, measured_at: datetime) -> None:
    """R3: the measurement state comes only from applied revisions (no conflicts or duplicates)."""
    applied = db.scalars(
        select(ReportRevision)
        .join(ReportRevision.report_raw)
        .where(
            ReportRevision.trainset_id == trainset_id,
            ReportRevision.measured_at == measured_at,
            ReportRaw.status == ReportStatus.APPLIED,
        )
        .options(selectinload(ReportRevision.metrics))
    ).all()
    state = apply_revisions(Revision(rev=r.rev, content=_content(r)) for r in applied)

    measurement = db.scalar(
        select(Measurement)
        .where(Measurement.trainset_id == trainset_id, Measurement.measured_at == measured_at)
        .options(selectinload(Measurement.metrics))
    )
    # Duty before the change: its rollups also change if the measurement leaves it (R7)
    old_duty_id = measurement.duty_id if measurement is not None else None

    if not state.metrics:
        # Without metrics the measurement does not appear (R3)
        if measurement is not None:
            db.delete(measurement)
            db.flush()
            refresh_rollups(db, [old_duty_id])
        return

    if measurement is None:
        measurement = Measurement(trainset_id=trainset_id, measured_at=measured_at)
        db.add(measurement)
    measurement.station_id = state.station
    # R5: duty of this trainset's assignment covering measured_at (None = unassigned)
    measurement.duty_id = find_duty(measured_at, assignment_periods(db, trainset_id))
    # Synchronizes metrics: updates those that remain, deletes those that left, adds new ones
    current = {metric.metric: metric for metric in measurement.metrics}
    for name, metric in current.items():
        if name in state.metrics:
            metric.value = state.metrics[name]
        else:
            measurement.metrics.remove(metric)
    for name, value in state.metrics.items():
        if name not in current:
            measurement.metrics.append(MeasurementMetric(metric=name, value=value))

    db.flush()  # rollups are computed from the already stored measurements
    refresh_rollups(db, [old_duty_id, measurement.duty_id])
