from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.models.enums import QuarantineReason, ReportStatus


class ReportAcceptedResponse(BaseModel):
    report_id: int


class ReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    raw_content: str
    received_at: AwareDatetime
    status: ReportStatus
    quarantine_reason: QuarantineReason | None
    batch_id: int | None
    batch_line: int | None


class ReportQuarantineResponse(BaseModel):
    reason: QuarantineReason
    raw_line: str
    source: str
    received_at: AwareDatetime