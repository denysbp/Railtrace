from fastapi import (
    Depends,
    APIRouter,
    status,
    File,
    UploadFile,
    HTTPException
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from app.models.batch import Batch
from app.models.enums import ReportStatus
from app.models.report_raw import ReportRaw
from app.schemas.batch import BatchResponse, BatchStatsResponse
from app.services.ingest import ingest_batch
from app.db.session import get_db

MAX_BATCH_SIZE = 5 * 1024 * 1024  # 5 MB

depot_router = APIRouter(
    prefix="/depot",
    tags=["Depot"]
)

@depot_router.post(
    "/batches",
    response_model=BatchResponse,
    status_code=status.HTTP_202_ACCEPTED
)
def upload_batch(
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    if file.size > MAX_BATCH_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Batch exceeds the 5 MB limit"
        )
    try:
        batch_id = ingest_batch(db, file.filename, file.file)
    except UnicodeDecodeError:
        # o commit só é feito no fim do ingest, por isso não fica nada gravado
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch must be UTF-8 encoded"
        )
    return BatchResponse(batch_id=batch_id)


@depot_router.get(
    "/batches/{batch_id}",
    response_model=BatchStatsResponse
)
def get_batch(
    batch_id: int,
    db: Session = Depends(get_db)
):
    if db.get(Batch, batch_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )

    # Só leitura: conta os reports_raw do batch por status e motivo de quarentena
    rows = db.execute(
        select(ReportRaw.status, ReportRaw.quarantine_reason, func.count())
        .where(ReportRaw.batch_id == batch_id)
        .group_by(ReportRaw.status, ReportRaw.quarantine_reason)
    ).all()

    stats = BatchStatsResponse(
        batch_id=batch_id,
        lines=0,
        applied=0,
        duplicate=0,
        pending=0,
        quarantined={}
    )
    for report_status, reason, count in rows:
        stats.lines += count
        if report_status == ReportStatus.APPLIED:
            stats.applied += count
        elif report_status == ReportStatus.DUPLICATE:
            stats.duplicate += count
        elif report_status == ReportStatus.PENDING:
            stats.pending += count
        elif report_status == ReportStatus.QUARANTINED:
            stats.quarantined[reason.value] = count
    return stats
