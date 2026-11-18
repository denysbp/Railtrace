from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.duty import Duty
    from app.models.trainset import Trainset

# Teoria dos conjuntos
_PERIOD = text("tstzrange(started_at, ended_at, '[)')")


class Assignment(Base):
    """Liga uma composição (Trainset) a uma Duty durante um intervalo."""

    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint("ended_at > started_at", name="ck_assignments_interval"),
        # Uma composição não pode estar em duas Duties ao mesmo tempo.
        ExcludeConstraint(
            ("trainset_id", "="),
            (_PERIOD, "&&"),
            name="ex_assignments_trainset_no_overlap",
            using="gist",
        ),
        # Uma Duty não pode ter duas composições ao mesmo tempo.
        ExcludeConstraint(
            ("duty_id", "="),
            (_PERIOD, "&&"),
            name="ex_assignments_duty_no_overlap",
            using="gist",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    trainset_id: Mapped[int] = mapped_column(
        ForeignKey("trainsets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    duty_id: Mapped[int] = mapped_column(
        ForeignKey("duties.id", ondelete="RESTRICT"),
        nullable=False,
    )

    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # NULL = assignment em aberto (sem fim); o tstzrange trata-o como intervalo infinito
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    trainset: Mapped["Trainset"] = relationship(back_populates="assignments")
    duty: Mapped["Duty"] = relationship(back_populates="assignments")
