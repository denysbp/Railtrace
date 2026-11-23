from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.line import Line
    from app.models.station import Station


class LineStation(Base):
    """Station on a line, with its position in the route (1 = first)."""

    __tablename__ = "line_stations"
    __table_args__ = (
        # Two stations cannot occupy the same position on the same line
        UniqueConstraint("line_id", "position", name="uq_line_stations_line_position"),
        CheckConstraint("position >= 1", name="ck_line_stations_position_positive"),
    )

    line_id: Mapped[int] = mapped_column(
        ForeignKey("lines.id", ondelete="CASCADE"),
        primary_key=True,
    )
    station_id: Mapped[int] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"),
        primary_key=True,
        index=True,  # the PK (line_id, station_id) cannot serve lookups by station_id alone
    )
    position: Mapped[int] = mapped_column(nullable=False)

    line: Mapped["Line"] = relationship(back_populates="station_links")
    station: Mapped["Station"] = relationship(back_populates="line_links")
