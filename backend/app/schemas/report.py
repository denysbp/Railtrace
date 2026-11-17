from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.models.enums import QuarantineReason, ReportStatus

# Não existe schema de request: POST /reports recebe text/plain,
# o corpo é lido como texto e guardado tal como chegou.


class ReportAcceptedResponse(BaseModel):
    """Corpo da resposta 202 Accepted: o relatório foi guardado, não processado."""

    report_id: int


class ReportResponse(BaseModel):
    """Leitura de um relatório original (ex.: listagem da quarentena)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    raw_content: str
    received_at: AwareDatetime
    status: ReportStatus
    quarantine_reason: QuarantineReason | None
