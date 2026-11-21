from datetime import date, datetime, time, timedelta, timezone
from fastapi import (
    Depends,
    APIRouter,
    status,
    Query,
    HTTPException
)
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models.duty import Duty
from app.models.line import Line
from app.schemas.assignment import AssignmentResponse, DutyAssignmentCreate
from app.schemas.duty import (
    DutyHourlyResponse,
    DutyReadingsResponse,
    DutyResponse,
    DutyStationsResponse,
    DutySummaryResponse,
    DutyWithAssignmentsResponse,
)
from app.services import read_models
from app.services.read_models import UnknownMetricError
from app.services.assignments import (
    AssignmentOverlapError,
    DutyNotFoundError,
    TrainsetNotFoundError,
    TrainsetWrongLineError,
    create_assignment,
)
from app.db.session import get_db

duties_router = APIRouter(
    prefix="/duties",
    tags=["Duties"]
)

@duties_router.get(
    "",
    response_model=list[DutyResponse]
)
def list_duties(
    day: date = Query(..., alias="date", description="YYYY-MM-DD"),
    line: str | None = Query(None, description="Código da linha (ex.: AZ)"),
    db: Session = Depends(get_db)
):
    start = datetime.combine(day, time.min, tzinfo=timezone.utc)
    query = (
        select(Duty)
        .where(Duty.planned_start >= start, Duty.planned_start < start + timedelta(days=1))
        .order_by(Duty.planned_start, Duty.code)
    )
    if line is not None:
        query = query.join(Duty.line).where(Line.code == line)
    return db.scalars(query).all()


@duties_router.get(
    "/{code}",
    response_model=DutyWithAssignmentsResponse
)
def get_duty(
    code: str,
    db: Session = Depends(get_db)
):
    # Só leitura: a duty e os seus assignments, por ordem de início
    duty = db.scalar(
        select(Duty)
        .where(Duty.code == code)
        .options(selectinload(Duty.assignments))
    )
    if duty is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Duty not found"
        )
    duty.assignments.sort(key=lambda assignment: assignment.started_at)
    return duty


@duties_router.post(
    "/{code}/assignments",
    response_model=AssignmentResponse,
    status_code=status.HTTP_201_CREATED
)
def add_assignment(
    code: str,
    body: DutyAssignmentCreate,
    db: Session = Depends(get_db)
):
    # As regras estão no serviço; aqui só se traduzem os erros em HTTP
    try:
        return create_assignment(db, code, body.trainset, body.started_at, body.ended_at)
    except DutyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Duty not found"
        )
    except TrainsetNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Trainset not found"
        )
    except TrainsetWrongLineError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Trainset belongs to another line"
        )
    except AssignmentOverlapError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Assignment overlaps an existing one"
        )


# --- Read models (R7): só leitura, as consultas estão em services/read_models.py

def _read(query, *args):
    try:
        return query(*args)
    except DutyNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Duty not found"
        )
    except UnknownMetricError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Unknown metric"
        )


@duties_router.get(
    "/{code}/readings",
    response_model=DutyReadingsResponse
)
def get_duty_readings(
    code: str,
    metric: str = Query(..., description="Ex.: SPD, KWH, AX1"),
    db: Session = Depends(get_db)
):
    return _read(read_models.duty_readings, db, code, metric)


@duties_router.get(
    "/{code}/hourly",
    response_model=DutyHourlyResponse
)
def get_duty_hourly(
    code: str,
    metric: str = Query(..., description="Ex.: SPD, KWH, AX1"),
    db: Session = Depends(get_db)
):
    return _read(read_models.duty_hourly, db, code, metric)


@duties_router.get(
    "/{code}/summary",
    response_model=DutySummaryResponse
)
def get_duty_summary(
    code: str,
    db: Session = Depends(get_db)
):
    return _read(read_models.duty_summary, db, code)


@duties_router.get(
    "/{code}/stations",
    response_model=DutyStationsResponse
)
def get_duty_stations(
    code: str,
    db: Session = Depends(get_db)
):
    return _read(read_models.duty_stations, db, code)
