from fastapi import (
    Depends,
    APIRouter
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models.line import Line
from app.schemas.line import LineWithStationsResponse
from app.db.session import get_db

lines_router = APIRouter(
    prefix="/lines",
    tags=["Lines"]
)

@lines_router.get(
    "",
    response_model=list[LineWithStationsResponse]
)
def list_lines(
    db: Session = Depends(get_db)
):
    # Read-only. Line.stations is already ordered by LineStation.position;
    # selectinload loads the stations of all lines in a single extra query.
    return db.scalars(
        select(Line)
        .options(selectinload(Line.stations))
        .order_by(Line.id)
    ).all()
