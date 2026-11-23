from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import QuarantineReason, ReportStatus

if TYPE_CHECKING:
    from app.models.batch import Batch
    from app.models.report_revision import ReportRevision


def _enum_values(enum_cls: type) -> list[str]:
    # Stores the value ("pending") in the DB instead of the member name ("PENDING").
    return [member.value for member in enum_cls]


class ReportRaw(Base):
    __tablename__ = "reports_raw"
    __table_args__ = (
        # quarantine_reason set <=> status = quarantined
        CheckConstraint(
            "(status = 'quarantined') = (quarantine_reason IS NOT NULL)",
            name="ck_reports_raw_quarantine_reason",
        ),
        # batch_line only exists (and is required) when the report came from a batch
        CheckConstraint(
            "(batch_id IS NULL) = (batch_line IS NULL)",
            name="ck_reports_raw_batch_line",
        ),
        CheckConstraint("batch_line >= 1", name="ck_reports_raw_batch_line_positive"),
        # The same file line cannot be stored twice in the same batch
        UniqueConstraint("batch_id", "batch_line", name="uq_reports_raw_batch_line"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    raw_content: Mapped[str] = mapped_column(Text, nullable=False)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    status: Mapped[ReportStatus] = mapped_column(
        SQLAlchemyEnum(ReportStatus, name="report_status", values_callable=_enum_values),
        nullable=False,
        default=ReportStatus.PENDING,
        server_default=ReportStatus.PENDING.value,
        index=True,
    )

    quarantine_reason: Mapped[QuarantineReason | None] = mapped_column(
        SQLAlchemyEnum(QuarantineReason, name="quarantine_reason", values_callable=_enum_values),
        nullable=True,
    )

    # NULL = sent on its own in real time (POST /v1/reports)
    batch_id: Mapped[int | None] = mapped_column(
        # append-only: a batch with reports is not deleted
        ForeignKey("batches.id", ondelete="RESTRICT", name="fk_reports_raw_batch_id_batches"),
        nullable=True,
    )
    # Line number in the original file (1 = first line), for traceability
    batch_line: Mapped[int | None] = mapped_column(nullable=True)

    batch: Mapped["Batch | None"] = relationship(back_populates="reports")
    # Revision created from this report (None if not processed yet or quarantined)
    revision: Mapped["ReportRevision | None"] = relationship(back_populates="report_raw")
