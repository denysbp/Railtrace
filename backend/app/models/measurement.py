from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Measurement(Base):
    """Effective state of a measurement after valid revisions have been applied."""

    __tablename__ = "measurements"
    __table_args__ = (
        UniqueConstraint("trainset_id", "measured_at", name="uq_measurements_trainset_measured_at"),
        Index("ix_measurements_duty_measured_at", "duty_id", "measured_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    trainset_id: Mapped[int] = mapped_column(
        ForeignKey("trainsets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL = measurement without a station ("-" in the report)
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    # NULL = measurement not assigned to any duty
    duty_id: Mapped[int | None] = mapped_column(
        ForeignKey("duties.id", ondelete="RESTRICT"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    metrics: Mapped[list["MeasurementMetric"]] = relationship(
        back_populates="measurement",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class MeasurementMetric(Base):
    """Effective value of a metric in a measurement."""

    __tablename__ = "measurement_metrics"
    __table_args__ = (
        # Lookups by metric (the PK starts with measurement_id and cannot serve this)
        Index("ix_measurement_metrics_metric", "metric", "measurement_id"),
    )

    measurement_id: Mapped[int] = mapped_column(
        ForeignKey("measurements.id", ondelete="CASCADE"),
        primary_key=True,
    )
    metric: Mapped[str] = mapped_column(String(16), primary_key=True)
    # Numeric without fixed precision: stores the value exactly as received
    value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    measurement: Mapped["Measurement"] = relationship(back_populates="metrics")
