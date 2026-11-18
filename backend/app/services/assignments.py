from datetime import datetime

from psycopg.errors import ExclusionViolation
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.assignment import Assignment
from app.models.duty import Duty
from app.models.trainset import Trainset


class DutyNotFoundError(Exception):
    pass


class TrainsetNotFoundError(Exception):
    pass


class TrainsetWrongLineError(Exception):
    pass


class AssignmentOverlapError(Exception):
    pass


def create_assignment(
    db: Session,
    duty_code: str,
    trainset_serial: str,
    started_at: datetime,
    ended_at: datetime | None,
) -> Assignment:
    """Liga uma composição a uma duty.

    Regras:
    - a composição tem de ser da mesma linha da duty;
    - não pode sobrepor outro assignment da mesma composição nem da mesma duty
      (garantido na BD pelas ExcludeConstraint).
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
    try:
        db.add(assignment)
        db.commit()
    except IntegrityError as e:
        db.rollback()
        if isinstance(e.orig, ExclusionViolation):
            raise AssignmentOverlapError from e
        raise
    return assignment
