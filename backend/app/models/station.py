from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.line import Line
    from app.models.line_station import LineStation


class Station(Base):
    """Physical station (e.g. SSE - Saldanha).

    An interchange station exists only once and connects to several
    lines through LineStation.
    """

    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    line_links: Mapped[list["LineStation"]] = relationship(
        back_populates="station",
        cascade="all, delete-orphan",
    )
    # Read-only shortcut: lines that pass through this station
    lines: Mapped[list["Line"]] = relationship(
        secondary="line_stations",
        viewonly=True,
    )
