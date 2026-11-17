from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Enum as SQLAlchemyEnum, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import QuarantineReason, ReportStatus


def _enum_values(enum_cls: type) -> list[str]:
    # Grava na BD o valor ("pending") em vez do nome do membro ("PENDING").
    return [member.value for member in enum_cls]


class ReportRaw(Base):
    """Relatório tal como foi recebido pela API (append-only).

    A API só grava raw_content. O Worker faz o parsing depois e só
    altera status / quarantine_reason; raw_content nunca é alterado.
    """

    __tablename__ = "reports_raw"
    __table_args__ = (
        # quarantine_reason preenchido <=> status = quarantined
        CheckConstraint(
            "(status = 'quarantined') = (quarantine_reason IS NOT NULL)",
            name="ck_reports_raw_quarantine_reason",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    raw_content: Mapped[str] = mapped_column(Text, nullable=False)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    status: Mapped[ReportStatus] = mapped_column(
        SQLAlchemyEnum(ReportStatus, name="report_status", values_callable=_enum_values),
        nullable=False,
        default=ReportStatus.PENDING,
        server_default=ReportStatus.PENDING.value,
        index=True,
    )

    quarantine_reason: Mapped[QuarantineReason | None] = mapped_column(
        SQLAlchemyEnum(QuarantineReason, name="quarantine_reason", values_callable=_enum_values),
        nullable=True,
    )
