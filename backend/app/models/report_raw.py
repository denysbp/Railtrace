from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum as SQLAlchemyEnum,
    ForeignKey,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import QuarantineReason, ReportStatus

if TYPE_CHECKING:
    from app.models.batch import Batch
    from app.models.report_revision import ReportRevision


def _enum_values(enum_cls: type) -> list[str]:
    # Grava na BD o valor ("pending") em vez do nome do membro ("PENDING").
    return [member.value for member in enum_cls]


class ReportRaw(Base):
    """
    Relatório tal como foi recebido pela API (append-only).

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
        # batch_line só existe (e é obrigatório) quando o relatório veio de um batch
        CheckConstraint(
            "(batch_id IS NULL) = (batch_line IS NULL)",
            name="ck_reports_raw_batch_line",
        ),
        CheckConstraint("batch_line >= 1", name="ck_reports_raw_batch_line_positive"),
        # A mesma linha do ficheiro não pode ser gravada duas vezes no mesmo batch
        UniqueConstraint("batch_id", "batch_line", name="uq_reports_raw_batch_line"),
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

    # NULL = enviado sozinho em tempo real (POST /v1/reports)
    batch_id: Mapped[int | None] = mapped_column(
        # append-only: não se apaga um batch com relatórios
        ForeignKey("batches.id", ondelete="RESTRICT", name="fk_reports_raw_batch_id_batches"),
        nullable=True,
    )
    # Número da linha no ficheiro original (1 = primeira linha), para rastreabilidade
    batch_line: Mapped[int | None] = mapped_column(nullable=True)

    batch: Mapped["Batch | None"] = relationship(back_populates="reports")
    # Revisão criada a partir deste relatório (None se ainda não foi processado ou ficou em quarentena)
    revision: Mapped["ReportRevision | None"] = relationship(back_populates="report_raw")
