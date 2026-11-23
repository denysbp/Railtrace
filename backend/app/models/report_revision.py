from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.report_raw import ReportRaw


class ReportRevision(Base):
    """
    Valid report already interpreted (a revision of a measurement).

    There is no UNIQUE on (trainset_id, measured_at, rev): R4 allows several
    reports with the same identity when there is a conflict, and candidates
    must be kept stored so the conflict can be detected.
    """

    __tablename__ = "report_revisions"
    __table_args__ = (
        CheckConstraint("rev >= 0", name="ck_report_revisions_rev_non_negative"),
        # Lookup of the revisions of a measurement (identity + rev)
        Index("ix_report_revisions_identity", "trainset_id", "measured_at", "rev"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Each original report yields at most one revision
    report_raw_id: Mapped[int] = mapped_column(
        ForeignKey("reports_raw.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    trainset_id: Mapped[int] = mapped_column(
        ForeignKey("trainsets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rev: Mapped[int] = mapped_column(nullable=False)
    # NULL = report without a station ("-" in the report)
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    report_raw: Mapped["ReportRaw"] = relationship(back_populates="revision")
    metrics: Mapped[list["ReportRevisionMetric"]] = relationship(
        back_populates="report_revision",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# This model exists so that if a new metric appears we do not have
# to change the table.
class ReportRevisionMetric(Base):
    """Value of a metric received in a revision."""

    __tablename__ = "report_revision_metrics"

    report_revision_id: Mapped[int] = mapped_column(
        ForeignKey("report_revisions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    metric: Mapped[str] = mapped_column(String(16), primary_key=True)
    # Numeric without fixed precision: stores the value exactly as received
    # And NULL to follow removal rules such as R3
    value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    report_revision: Mapped["ReportRevision"] = relationship(back_populates="metrics")
