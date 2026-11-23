from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.duty import Duty
    from app.models.line_station import LineStation
    from app.models.station import Station
    from app.models.trainset import Trainset


class Line(Base):
    __tablename__ = "lines"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(2), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    trainsets: Mapped[list["Trainset"]] = relationship(back_populates="home_line")
    duties: Mapped[list["Duty"]] = relationship(back_populates="line")

    station_links: Mapped[list["LineStation"]] = relationship(
        back_populates="line",
        order_by="LineStation.position",
        cascade="all, delete-orphan",
    )
    # stations of the line, in route order
    stations: Mapped[list["Station"]] = relationship(
        secondary="line_stations",
        order_by="LineStation.position",
        viewonly=True,
    )
