from fastapi import (
    Depends,
    APIRouter,
    HTTPException,
    status
)
from app.models import Trainset, Line
from app.schemas.trainset import (
    TrainsetCreate,
    TrainsetResponse
)
from sqlalchemy.orm import Session
from app.db.session import get_db
from sqlalchemy import select

trainset_router = APIRouter(
    prefix="/trainsets",
    tags=["Trainsets"]
)


@trainset_router.post(
    "",
    response_model=TrainsetResponse,
    status_code=status.HTTP_201_CREATED
)
def create_trainset(
    body: TrainsetCreate,
    db: Session = Depends(get_db)
):
    query = db.scalar(select(Trainset).where(Trainset.serial == body.serial))
    if query:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The trainset {body.serial} already exist"
        )
    home_line = db.scalar(select(Line).where(Line.code == body.line))
    if not home_line:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Line {body.home_line_code} don't exist"
        )
    try:
        trainset = Trainset(
            serial=body.serial,
            home_line_id=home_line.id
        )
        db.add(trainset)
        db.commit()
        db.refresh(trainset)
    except Exception:
        db.rollback()
        raise
    return trainset