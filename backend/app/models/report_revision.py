from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.report_raw import ReportRaw


class ReportRevision(Base):
    """
    Relatório válido já interpretado (uma revisão de uma medição).

    Não há UNIQUE em (trainset_id, measured_at, rev): a R4 permite vários
    relatórios com a mesma identidade quando há conflito, e os candidatos
    têm de ficar guardados para o conflito poder ser detetado.
    """

    __tablename__ = "report_revisions"
    __table_args__ = (
        CheckConstraint("rev >= 0", name="ck_report_revisions_rev_non_negative"),
        # Procura das revisões de uma medição (identidade + rev)
        Index("ix_report_revisions_identity", "trainset_id", "measured_at", "rev"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # Cada relatório original dá no máximo uma revisão
    report_raw_id: Mapped[int] = mapped_column(
        ForeignKey("reports_raw.id", ondelete="RESTRICT"),
        unique=True,
        nullable=False,
    )
    trainset_id: Mapped[int] = mapped_column(
        ForeignKey("trainsets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    rev: Mapped[int] = mapped_column(nullable=False)
    # NULL = relatório sem estação ("-" no relatório)
    station_id: Mapped[int | None] = mapped_column(
        ForeignKey("stations.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    report_raw: Mapped["ReportRaw"] = relationship(back_populates="revision")
    metrics: Mapped[list["ReportRevisionMetric"]] = relationship(
        back_populates="report_revision",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


# Fiz esse modelo pq se surgir uma nova metrica nao temos
# de alterar a tabela.
class ReportRevisionMetric(Base):
    """Valor de uma métrica recebido numa revisão."""

    __tablename__ = "report_revision_metrics"

    report_revision_id: Mapped[int] = mapped_column(
        ForeignKey("report_revisions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    metric: Mapped[str] = mapped_column(String(16), primary_key=True)
    # Numeric sem precisão fixa: guarda o valor exatamente como foi recebido
    # E NULL para seguir as regras de remocao tipo R3
    value: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)

    report_revision: Mapped["ReportRevision"] = relationship(back_populates="metrics")
