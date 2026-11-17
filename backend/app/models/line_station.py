from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.line import Line
    from app.models.station import Station


class LineStation(Base):
    """Estação numa linha, com a sua posição no percurso (1 = primeira)."""

    __tablename__ = "line_stations"
    __table_args__ = (
        # Duas estações não podem ocupar a mesma posição na mesma linha
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
        index=True,  # a PK (line_id, station_id) não serve pesquisas só por station_id
    )
    position: Mapped[int] = mapped_column(nullable=False)

    line: Mapped["Line"] = relationship(back_populates="station_links")
    station: Mapped["Station"] = relationship(back_populates="line_links")
