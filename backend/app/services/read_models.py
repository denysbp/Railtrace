from datetime import datetime, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.domain import METRIC_STRATEGIES
from app.models import (
    Batch,
    Duty,
    DutyHourlyRollup,
    DutyMetricSummary,
    DutyStationStats,
    Line,
    Measurement,
    MeasurementMetric,
    QuarantineReason,
    ReportOutcome,
    ReportRaw,
    ReportStatus,
    Station,
    Trainset,
)
from app.services.assignments import DutyNotFoundError


class UnknownMetricError(Exception):
    pass


def _duty(db: Session, code: str) -> Duty:
    duty = db.scalar(select(Duty).where(Duty.code == code))
    if duty is None:
        raise DutyNotFoundError
    return duty


def _check_metric(metric: str) -> None:
    if metric not in METRIC_STRATEGIES:
        raise UnknownMetricError


def _utc(instant: datetime) -> datetime:
    return instant.astimezone(timezone.utc)


def duty_readings(db: Session, code: str, metric: str) -> dict:
    """Valores de uma métrica nas medições da duty, por ordem temporal."""
    _check_metric(metric)
    duty = _duty(db, code)
    rows = db.execute(
        select(Measurement.measured_at, MeasurementMetric.value, Trainset.serial, Station.code)
        .join(MeasurementMetric, MeasurementMetric.measurement_id == Measurement.id)
        .join(Trainset, Trainset.id == Measurement.trainset_id)
        .outerjoin(Station, Station.id == Measurement.station_id)
        .where(
            Measurement.duty_id == duty.id,
            MeasurementMetric.metric == metric,
            MeasurementMetric.value.is_not(None),
        )
        .order_by(Measurement.measured_at, Trainset.serial)
    ).all()
    return {
        "duty": code,
        "metric": metric,
        "points": [
            {
                "measured_at": _utc(measured_at),
                "value": float(value),
                "trainset": serial,
                "station": station
            }
            for measured_at, value, serial, station in rows
        ],
    }


def duty_hourly(db: Session, code: str, metric: str) -> dict:
    """Rollups por hora UTC de uma métrica (R7)."""
    _check_metric(metric)
    duty = _duty(db, code)
    rows = db.scalars(
        select(DutyHourlyRollup)
        .where(DutyHourlyRollup.duty_id == duty.id, DutyHourlyRollup.metric == metric)
        .order_by(DutyHourlyRollup.hour)
    ).all()
    return {
        "duty": code,
        "metric": metric,
        "buckets": [
            {"hour": _utc(r.hour), "count": r.count, "value": float(r.value), "coverage": float(r.coverage)}
            for r in rows
        ],
    }


def duty_summary(db: Session, code: str) -> dict:
    """Composições, número de medições e resumo por métrica da duty inteira (R7)."""
    duty = _duty(db, code)
    trainsets = db.scalars(
        select(Trainset.serial)
        .join(Measurement, Measurement.trainset_id == Trainset.id)
        .where(Measurement.duty_id == duty.id)
        .distinct()
        .order_by(Trainset.serial)
    ).all()
    measurements = db.scalar(select(func.count()).select_from(Measurement).where(Measurement.duty_id == duty.id))
    values = dict(
        db.execute(
            select(DutyMetricSummary.metric, DutyMetricSummary.value).where(DutyMetricSummary.duty_id == duty.id)
        ).all()
    )
    # pela ordem do registo de métricas (SPD, KWH, AX1..AX8)
    metrics = {metric: float(values[metric]) for metric in METRIC_STRATEGIES if metric in values}
    return {"duty": code, "trainsets": list(trainsets), "measurements": measurements, "metrics": metrics}


def duty_stations(db: Session, code: str) -> dict:
    """Todas as estações da linha da duty, pela ordem do percurso, com os rollups (R7).

    Uma estação sem medições na duty aparece com reports 0 e max_axle None.
    """
    duty = _duty(db, code)
    line = db.get(Line, duty.line_id)
    stats = {
        row.station_id: row
        for row in db.scalars(select(DutyStationStats).where(DutyStationStats.duty_id == duty.id))
    }
    stations = []
    for station in line.stations:  # já ordenadas por LineStation.position
        row = stats.get(station.id)
        stations.append({
            "station": station.code,
            "name": station.name,
            "reports": row.reports if row else 0,
            "max_axle": float(row.max_axle) if row and row.max_axle is not None else None,
        })
    return {"duty": code, "line": line.code, "stations": stations}


def _received(db: Session, *where) -> int:
    """Quantos relatórios foram recebidos (só conta linhas da fila reports_raw)."""
    return db.scalar(select(func.count()).select_from(ReportRaw).where(*where))


def _outcome_counts(db: Session, *where) -> tuple[int, int, int, dict[str, int]]:
    """(processados, applied, duplicate, {motivo: n}) a partir do read model report_outcomes."""
    applied = duplicate = processed = 0
    quarantined: dict[str, int] = {}
    rows = db.execute(
        select(ReportOutcome.status, ReportOutcome.quarantine_reason, func.count())
        .where(*where)
        .group_by(ReportOutcome.status, ReportOutcome.quarantine_reason)
        .order_by(ReportOutcome.quarantine_reason)
    ).all()
    for status, reason, count in rows:
        processed += count
        if status == ReportStatus.APPLIED:
            applied += count
        elif status == ReportStatus.DUPLICATE:
            duplicate += count
        elif status == ReportStatus.QUARANTINED:
            quarantined[reason.value] = count
    return processed, applied, duplicate, quarantined


class BatchNotFoundError(Exception):
    pass


def batch_outcome(db: Session, batch_id: int) -> dict:
    """Resultado atual de cada relatório do batch. pending = recebidos ainda sem resultado."""
    if db.get(Batch, batch_id) is None:
        raise BatchNotFoundError
    lines = _received(db, ReportRaw.batch_id == batch_id)
    processed, applied, duplicate, quarantined = _outcome_counts(db, ReportOutcome.batch_id == batch_id)
    return {
        "batch_id": batch_id,
        "lines": lines,
        "applied": applied,
        "duplicate": duplicate,
        "pending": lines - processed,
        "quarantined": quarantined,
    }


def quarantine_list(db: Session, reason: QuarantineReason, limit: int) -> list[dict]:
    """Relatórios em quarentena com esse motivo, os mais recentes primeiro."""
    rows = db.scalars(
        select(ReportOutcome)
        .where(ReportOutcome.status == ReportStatus.QUARANTINED, ReportOutcome.quarantine_reason == reason)
        .order_by(ReportOutcome.received_at.desc(), ReportOutcome.report_raw_id.desc())
        .limit(limit)
    ).all()
    return [
        {
            "reason": row.quarantine_reason,
            "raw_line": row.raw_line,
            "source": "live" if row.batch_id is None else f"batch:{row.batch_id}:line:{row.batch_line}",
            "received_at": _utc(row.received_at),
        }
        for row in rows
    ]


def stats(db: Session) -> dict:
    """Totais. Resultados dos relatórios e medições vêm dos read models;
    de reports_raw só se conta quantos foram recebidos (pending = recebidos - processados)."""
    reports_total = _received(db)
    processed, _, _, quarantined = _outcome_counts(db)
    measurements, attributed = db.execute(
        select(func.count(), func.count(Measurement.duty_id)).select_from(Measurement)
    ).one()
    return {
        "reports_total": reports_total,
        "measurements": measurements,
        "attributed": attributed,
        "unattributed": measurements - attributed,
        "quarantined": quarantined,
        "pending": reports_total - processed,
    }
