"""Importa todos os modelos para que fiquem registados em Base.metadata
(necessário para o Alembic autogenerate e para resolver as relationships)."""

from app.models.assignment import Assignment
from app.models.base import Base
from app.models.batch import Batch
from app.models.duty import Duty
from app.models.enums import QuarantineReason, ReportStatus
from app.models.line import Line
from app.models.line_station import LineStation
from app.models.measurement import Measurement, MeasurementMetric
from app.models.report_raw import ReportRaw
from app.models.report_revision import ReportRevision, ReportRevisionMetric
from app.models.rollup import DutyHourlyRollup, DutyMetricSummary, DutyStationStats
from app.models.station import Station
from app.models.trainset import Trainset

__all__ = [
    "Assignment",
    "Base",
    "Batch",
    "Duty",
    "DutyHourlyRollup",
    "DutyMetricSummary",
    "DutyStationStats",
    "Line",
    "LineStation",
    "Measurement",
    "MeasurementMetric",
    "QuarantineReason",
    "ReportRaw",
    "ReportRevision",
    "ReportRevisionMetric",
    "ReportStatus",
    "Station",
    "Trainset",
]
