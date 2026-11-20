from datetime import datetime
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.domain import AssignmentPeriod, find_duty
from app.models import Assignment, Measurement
from app.services.rollups import refresh_rollups


def assignment_periods(db: Session, trainset_id: int) -> list[AssignmentPeriod]:
    """Todos os assignments de uma composição, como períodos do domain."""
    rows = db.execute(
        select(Assignment.duty_id, Assignment.started_at, Assignment.ended_at)
        .where(Assignment.trainset_id == trainset_id)
    ).all()
    return [AssignmentPeriod(duty_id, started_at, ended_at) for duty_id, started_at, ended_at in rows]


def reattribute_measurements(db: Session, trainset_id: int, start: datetime, end: datetime) -> None:
    """Recalcula a duty das medições da composição com measured_at em [start, end).

    Usado quando um assignment é criado ou alterado. Não faz commit: corre na
    transação de quem chama. O assignment novo/alterado tem de já ter sido flushed.
    """
    periods = assignment_periods(db, trainset_id)
    measurements = db.scalars(
        select(Measurement).where(
            Measurement.trainset_id == trainset_id,
            Measurement.measured_at >= start,
            Measurement.measured_at < end,
        )
    ).all()
    # R7: os rollups mudam nas duties de onde as medições saem e para onde entram
    affected_duties = set()
    for measurement in measurements:
        new_duty_id = find_duty(measurement.measured_at, periods)
        if new_duty_id != measurement.duty_id:
            affected_duties.update({measurement.duty_id, new_duty_id})
            measurement.duty_id = new_duty_id
    db.flush()
    refresh_rollups(db, affected_duties)
