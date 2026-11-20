"""R7: recalcula os read models de rollups de uma duty a partir das suas medições.

Recalcular a duty inteira (em vez de atualizar incrementalmente) é simples e sempre
correto: uma duty tem poucas medições (~48), e qualquer alteração (correção, remoção,
conflito, reatribuição) fica refletida da mesma forma.
"""

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


def refresh_rollups(db: Session, duty_ids: Iterable[int | None]) -> None:
    """Recalcula os rollups das duties indicadas (None = não atribuída, ignorado).

    Não faz commit: corre na transação de quem chama. As medições alteradas têm de
    já ter sido flushed. Ordena os ids para que transações concorrentes bloqueiem as
    duties pela mesma ordem (evita deadlocks).
    """
    for duty_id in sorted({duty_id for duty_id in duty_ids if duty_id is not None}):
        _recompute_duty(db, duty_id)


def _recompute_duty(db: Session, duty_id: int) -> None:
    # Bloqueia a duty até ao fim da transação: dois recálculos da mesma duty
    # (Worker e API) não se cruzam no delete + insert.
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
