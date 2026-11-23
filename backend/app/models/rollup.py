from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class DutyHourlyRollup(Base):
    # Store metric aggregations for a duty, separated by hour.
    __tablename__ = "duty_hourly_rollups"
    __table_args__ = (
        CheckConstraint("count > 0", name="ck_duty_hourly_rollups_count_positive"),
    )

    duty_id: Mapped[int] = mapped_column(ForeignKey("duties.id", ondelete="CASCADE"), primary_key=True)
    metric: Mapped[str] = mapped_column(String(16), primary_key=True)
    hour: Mapped[datetime] = mapped_column(DateTime(timezone=True), primary_key=True)
    count: Mapped[int] = mapped_column(nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    coverage: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)


class DutyMetricSummary(Base):
    # What was the overall result of a metric in the duty?
    __tablename__ = "duty_metric_summaries"
    __table_args__ = (
        CheckConstraint("count > 0", name="ck_duty_metric_summaries_count_positive"),
    )

    duty_id: Mapped[int] = mapped_column(ForeignKey("duties.id", ondelete="CASCADE"), primary_key=True)
    metric: Mapped[str] = mapped_column(String(16), primary_key=True)
    count: Mapped[int] = mapped_column(nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)


class DutyStationStats(Base):
    # What activity and maximum values were there at each station?
    __tablename__ = "duty_station_stats"
    __table_args__ = (
        CheckConstraint("reports > 0", name="ck_duty_station_stats_reports_positive"),
    )

    duty_id: Mapped[int] = mapped_column(ForeignKey("duties.id", ondelete="CASCADE"), primary_key=True)
    station_id: Mapped[int] = mapped_column(ForeignKey("stations.id", ondelete="RESTRICT"), primary_key=True)
    reports: Mapped[int] = mapped_column(nullable=False)
    # None = no AX* metric in the measurements at that station
    max_axle: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
