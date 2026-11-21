from fastapi import (
    Depends,
    APIRouter
)
from sqlalchemy.orm import Session
from app.schemas.stats import StatsResponse
from app.services import read_models
from app.db.session import get_db

stats_router = APIRouter(
    prefix="/stats",
    tags=["Stats"]
)


@stats_router.get(
    "",
    response_model=StatsResponse
)
def get_stats(
    db: Session = Depends(get_db)
):
    return read_models.stats(db)
