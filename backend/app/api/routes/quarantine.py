from fastapi import (
    Depends,
    APIRouter,
    status,
    Query
)
from app.schemas import ReportQuarantineResponse
from app.models import QuarantineReason, ReportStatus
from typing import List
from sqlalchemy.orm import Session
from app.models import ReportRaw
from sqlalchemy import select
from app.db.session import get_db

quarantine_router = APIRouter(
    prefix="/quarantine",
    tags=["Quarantines"]
)


@quarantine_router.get(
    "",
    response_model=List[ReportQuarantineResponse],
    status_code=status.HTTP_200_OK
)
def get_quarantines(
    reason: QuarantineReason = Query(..., description="Quarantine reason"),
    limit: int = Query(..., description="Número máximo de resultados"),
    db: Session = Depends(get_db)
):
    query = select(ReportRaw).where(
        ReportRaw.status == ReportStatus.QUARANTINED
    )

    if reason is not None:
        query = query.where(
            ReportRaw.quarantine_reason == reason
        )

    query = (
        query
        .order_by(ReportRaw.received_at.desc())
        .limit(limit)
    )

    reports = db.scalars(query).all()

    return [
        ReportQuarantineResponse(
            reason=report.quarantine_reason,
            raw_line=report.raw_content,
            source=(
                "live"
                if report.batch_id is None
                else f"batch:{report.batch_id}:line:{report.batch_line}"
            ),
            received_at=report.received_at
        )
        for report in reports
    ]
