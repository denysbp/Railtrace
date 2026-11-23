from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.assignment import Assignment
    from app.models.line import Line


class Duty(Base):
    """Planned service on a line (e.g. AZ-D01-20261102)."""

    __tablename__ = "duties"
    __table_args__ = (
        CheckConstraint("planned_end > planned_start", name="ck_duties_planned_interval"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)

    line_id: Mapped[int] = mapped_column(
        ForeignKey("lines.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    planned_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    planned_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    line: Mapped["Line"] = relationship(back_populates="duties")
    assignments: Mapped[list["Assignment"]] = relationship(back_populates="duty")
