from datetime import datetime

from psycopg.errors import ExclusionViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assignment import Assignment
from app.models.duty import Duty
from app.models.trainset import Trainset
from app.services.attribution import reattribute_measurements


class DutyNotFoundError(Exception):
    pass


class TrainsetNotFoundError(Exception):
    pass


class TrainsetWrongLineError(Exception):
    pass


class AssignmentOverlapError(Exception):
    pass


class AssignmentNotFoundError(Exception):
    pass


class InvalidIntervalError(Exception):
    pass


def create_assignment(
    db: Session,
    duty_code: str,
    trainset_serial: str,
    started_at: datetime,
    ended_at: datetime,
) -> Assignment:
    """Links a trainset to a duty.

    Rules:
    - the trainset must be on the same line as the duty;
    - it cannot overlap another assignment of the same trainset or the same duty
      (enforced in the DB by the ExcludeConstraints).
    """
    duty = db.scalar(select(Duty).where(Duty.code == duty_code))
    if duty is None:
        raise DutyNotFoundError

    trainset = db.scalar(select(Trainset).where(Trainset.serial == trainset_serial))
    if trainset is None:
        raise TrainsetNotFoundError
    if trainset.home_line_id != duty.line_id:
        raise TrainsetWrongLineError

    assignment = Assignment(
        trainset_id=trainset.id,
        duty_id=duty.id,
        started_at=started_at,
        ended_at=ended_at,
    )
    db.add(assignment)
    _flush_or_overlap(db)
    # R5: measurements of the trainset within the new interval now belong to this duty
    reattribute_measurements(db, trainset.id, started_at, ended_at)
    db.commit()
    return assignment


def update_assignment(
    db: Session,
    assignment_id: int,
    started_at: datetime | None,
    ended_at: datetime | None,
) -> Assignment:
    assignment = db.get(Assignment, assignment_id)
    if assignment is None:
        raise AssignmentNotFoundError

    if started_at is None:
        started_at = assignment.started_at
    if ended_at is None:
        ended_at = assignment.ended_at
    if ended_at <= started_at:
        raise InvalidIntervalError

    # R5: affected = measurements between the old and new intervals (those entering and those leaving)
    affected_start = min(assignment.started_at, started_at)
    affected_end = max(assignment.ended_at, ended_at)

    assignment.started_at = started_at
    assignment.ended_at = ended_at
    _flush_or_overlap(db)
    reattribute_measurements(db, assignment.trainset_id, affected_start, affected_end)
    db.commit()
    return assignment


def _flush_or_overlap(db: Session) -> None:
    """Sends the assignment to the DB; an overlap (ExcludeConstraint) raises AssignmentOverlapError."""
    try:
        db.flush()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, ExclusionViolation):
            raise AssignmentOverlapError from e
        raise
