from typing import List
from fastapi import (
    Depends,
    APIRouter,
    status,
    Query
)
from sqlalchemy.orm import Session
from app.schemas import ReportQuarantineResponse
from app.models import QuarantineReason
from app.services import read_models
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
    # Só leitura do read model report_outcomes (A2)
    return read_models.quarantine_list(db, reason, limit)
