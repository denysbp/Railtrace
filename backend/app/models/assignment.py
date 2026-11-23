from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, text
from sqlalchemy.dialects.postgresql import ExcludeConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.duty import Duty
    from app.models.trainset import Trainset

# Set theory
_PERIOD = text("tstzrange(started_at, ended_at, '[)')")


class Assignment(Base):
    """Links a trainset to a duty over an interval."""

    __tablename__ = "assignments"
    __table_args__ = (
        CheckConstraint("ended_at > started_at", name="ck_assignments_interval"),
        # A trainset cannot be in two duties at the same time.
        ExcludeConstraint(
            ("trainset_id", "="),
            (_PERIOD, "&&"),
            name="ex_assignments_trainset_no_overlap",
            using="gist",
        ),
        # A duty cannot have two trainsets at the same time.
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
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    trainset: Mapped["Trainset"] = relationship(back_populates="assignments")
    duty: Mapped["Duty"] = relationship(back_populates="assignments")
