from fastapi import (
    FastAPI,
    Depends,
    APIRouter,
    status,
    Request,
    HTTPException
)
from sqlalchemy.orm import Session
from app.models.report_raw import ReportRaw
from app.schemas.report import ReportAcceptedResponse
from app.db.session import get_db

MAX_REPORT_SIZE = 1024

reports_router = APIRouter(
    tags=["Reports"]
)

@reports_router.post(
    "/reports",
    response_model=ReportAcceptedResponse,
    status_code=status.HTTP_202_ACCEPTED
)
def report(request: Request, db: Session = Depends(get_db)):
    try:
        content = request.body()

        if len(content) > MAX_REPORT_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail="Report exceeds the 1 KB limit"
            )
        report_raw = ReportRaw(
            raw_content= content.decode()
        )
        db.add(report_raw)
        db.commit()
        db.refresh(report_raw)
        return ReportAcceptedResponse(report_id=report_raw.id)
    except Exception:
        db.rollback()
        raise