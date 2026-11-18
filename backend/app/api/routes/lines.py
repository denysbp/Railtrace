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
    # Só leitura. Line.stations já vem ordenado por LineStation.position;
    # selectinload carrega as estações de todas as linhas numa só query extra.
    return db.scalars(
        select(Line)
        .options(selectinload(Line.stations))
        .order_by(Line.id)
    ).all()
