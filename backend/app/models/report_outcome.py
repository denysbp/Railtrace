from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum as SQLAlchemyEnum, ForeignKey, Index, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import QuarantineReason, ReportStatus
from app.models.report_raw import _enum_values


class ReportOutcome(Base):
    """
    Result of each already processed report (A2).

    Written by the Worker in the same transaction in which it processes the report (and updated
    when R4 puts earlier reports in conflict). This is what the endpoints
    /depot/batches/{id}, /quarantine and /stats read instead of reports_raw.

    A report that has not been processed yet has no row here.
    """

    __tablename__ = "report_outcomes"
    __table_args__ = (
        CheckConstraint("status <> 'pending'", name="ck_report_outcomes_processed"),
        CheckConstraint(
            "(status = 'quarantined') = (quarantine_reason IS NOT NULL)",
            name="ck_report_outcomes_quarantine_reason",
        ),
        # GET /quarantine?reason=: by reason, most recent first
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
