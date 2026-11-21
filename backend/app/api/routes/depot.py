from fastapi import (
    Depends,
    APIRouter,
    status,
    File,
    UploadFile,
    HTTPException
)
from sqlalchemy.orm import Session
from app.schemas.batch import BatchResponse, BatchStatsResponse
from app.services import read_models
from app.services.ingest import ingest_batch
from app.services.read_models import BatchNotFoundError
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
    try:
        return read_models.batch_outcome(db, batch_id)
    except BatchNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Batch not found"
        )
