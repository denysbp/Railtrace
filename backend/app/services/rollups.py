from collections.abc import Iterable

from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session, selectinload

from app.domain import (
    MetricPoint,
    StationReading,
    duty_summary,
    hourly_rollups,
    station_stats,
)
from app.models import (
    Duty,
    DutyHourlyRollup,
    DutyMetricSummary,
    DutyStationStats,
    Measurement,
)


DEFERRED_KEY = "deferred_rollup_duties"


def refresh_rollups(db: Session, duty_ids: Iterable[int | None]) -> None:
    ids = {duty_id for duty_id in duty_ids if duty_id is not None}
    deferred = db.info.get(DEFERRED_KEY)
    if deferred is not None:
        deferred.update(ids)
        return
    for duty_id in sorted(ids):
        _recompute_duty(db, duty_id)


def defer_rollups(db: Session) -> None:
    """A partir daqui, refresh_rollups só junta as duties afetadas."""
    db.info[DEFERRED_KEY] = set()


def flush_deferred_rollups(db: Session) -> None:
    """Calcula uma vez cada duty junta desde defer_rollups e volta ao modo normal."""
    refresh_rollups_ids = db.info.pop(DEFERRED_KEY, set())
    refresh_rollups(db, refresh_rollups_ids)


def _recompute_duty(db: Session, duty_id: int) -> None:
    db.execute(select(Duty.id).where(Duty.id == duty_id).with_for_update())

    measurements = db.scalars(
        select(Measurement)
        .where(Measurement.duty_id == duty_id)
        .options(selectinload(Measurement.metrics))
    ).all()

    points = [
        MetricPoint(measurement.measured_at, metric.metric, metric.value)
        for measurement in measurements
        for metric in measurement.metrics
        if metric.value is not None
    ]
    readings = [
        StationReading(
            measurement.station_id,
            {metric.metric: metric.value for metric in measurement.metrics if metric.value is not None},
        )
        for measurement in measurements
        if measurement.station_id is not None
    ]

    for model in (DutyHourlyRollup, DutyMetricSummary, DutyStationStats):
        db.execute(delete(model).where(model.duty_id == duty_id))

    hourly = [
        {"duty_id": duty_id, "metric": r.metric, "hour": r.hour, "count": r.count, "value": r.value, "coverage": r.coverage}
        for r in hourly_rollups(points)
    ]
    summary = [
        {"duty_id": duty_id, "metric": s.metric, "count": s.count, "value": s.value}
        for s in duty_summary(points)
    ]
    stations = [
        {"duty_id": duty_id, "station_id": s.station, "reports": s.reports, "max_axle": s.max_axle}
        for s in station_stats(readings)
    ]
    if hourly:
        db.execute(insert(DutyHourlyRollup), hourly)
    if summary:
        db.execute(insert(DutyMetricSummary), summary)
    if stations:
        db.execute(insert(DutyStationStats), stations)
