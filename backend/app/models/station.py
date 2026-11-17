from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.line import Line
    from app.models.line_station import LineStation


class Station(Base):
    """Estação física (ex.: SSE - Saldanha).

    Uma estação de correspondência existe uma só vez e liga-se a várias
    linhas através de LineStation.
    """

    __tablename__ = "stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(3), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)

    line_links: Mapped[list["LineStation"]] = relationship(
        back_populates="station",
        cascade="all, delete-orphan",
    )
    # Atalho só de leitura: linhas que passam nesta estação
    lines: Mapped[list["Line"]] = relationship(
        secondary="line_stations",
        viewonly=True,
    )
