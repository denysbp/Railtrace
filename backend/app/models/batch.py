from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.report_raw import ReportRaw


class Batch(Base):

    __tablename__ = "batches"

    id: Mapped[int] = mapped_column(primary_key=True)

    # Identificador do ficheiro (ex.: "depot-batch-01"), usado nas estatísticas por batch
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    reports: Mapped[list["ReportRaw"]] = relationship(
        back_populates="batch",
        order_by="ReportRaw.batch_line",
        # O ORM não mexe nos relatórios ao apagar o batch (não põe batch_id = NULL);
        # a FK com RESTRICT recusa o delete na BD
        passive_deletes="all",
    )
