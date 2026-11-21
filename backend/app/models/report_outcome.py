from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum as SQLAlchemyEnum, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import QuarantineReason, ReportStatus
from app.models.report_raw import _enum_values


class ReportOutcome(Base):
    """
    resultado de cada relatório já processado (A2).

    Escrito pelo Worker na mesma transação em que processa o relatório (e atualizado
    quando a R4 põe relatórios anteriores em conflito). É o que leem os endpoints
    /depot/batches/{id}, /quarantine e /stats, em vez de reports_raw.

    Um relatório ainda não processado não tem linha aqui.
    """

    __tablename__ = "report_outcomes"
    __table_args__ = (
        CheckConstraint("status <> 'pending'", name="ck_report_outcomes_processed"),
        CheckConstraint(
            "(status = 'quarantined') = (quarantine_reason IS NOT NULL)",
            name="ck_report_outcomes_quarantine_reason",
        ),
        # GET /quarantine?reason=: por motivo, os mais recentes primeiro
        Index("ix_report_outcomes_reason_received_at", "quarantine_reason", "received_at"),
    )

    report_raw_id: Mapped[int] = mapped_column(
        ForeignKey("reports_raw.id", ondelete="CASCADE"),
        primary_key=True,
    )
    batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("batches.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    batch_line: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[ReportStatus] = mapped_column(
        SQLAlchemyEnum(ReportStatus, name="report_status", values_callable=_enum_values),
        nullable=False,
    )
    quarantine_reason: Mapped[QuarantineReason | None] = mapped_column(
        SQLAlchemyEnum(QuarantineReason, name="quarantine_reason", values_callable=_enum_values),
        nullable=True,
    )
    raw_line: Mapped[str] = mapped_column(Text, nullable=False)
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
