"""Importa todos os modelos para que fiquem registados em Base.metadata
(necessário para o Alembic autogenerate e para resolver as relationships)."""

from app.models.assignment import Assignment
from app.models.base import Base
from app.models.duty import Duty
from app.models.enums import QuarantineReason, ReportStatus
from app.models.line import Line
from app.models.report_raw import ReportRaw
from app.models.trainset import Trainset

__all__ = [
    "Assignment",
    "Base",
    "Duty",
    "Line",
    "QuarantineReason",
    "ReportRaw",
    "ReportStatus",
    "Trainset",
]
