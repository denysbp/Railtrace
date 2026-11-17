from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.line import Line


class Trainset(Base):
    __tablename__ = "trainsets"

    id: Mapped[int] = mapped_column(primary_key=True)
    serial: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)

    home_line_id: Mapped[int] = mapped_column(
        ForeignKey("lines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    home_line: Mapped["Line"] = relationship(back_populates="trainsets")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="trainset")
