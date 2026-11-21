from pydantic import AwareDatetime, BaseModel, ConfigDict

from app.schemas.assignment import AssignmentResponse


class DutyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    line_id: int
    planned_start: AwareDatetime
    planned_end: AwareDatetime


class DutyWithAssignmentsResponse(DutyResponse):
    assignments: list[AssignmentResponse]


# --- Read models (R7) ---------------------------------------------------------
# Valores como float: o Pydantic serializa Decimal como texto, e a API devolve números.

class ReadingPoint(BaseModel):
    measured_at: AwareDatetime
    value: float
    trainset: str
    station: str | None


class DutyReadingsResponse(BaseModel):
    duty: str
    metric: str
    points: list[ReadingPoint]


class HourlyBucket(BaseModel):
    hour: AwareDatetime
    count: int
    value: float
    coverage: float


class DutyHourlyResponse(BaseModel):
    duty: str
    metric: str
    buckets: list[HourlyBucket]


class DutySummaryResponse(BaseModel):
    duty: str
    trainsets: list[str]
    measurements: int
    metrics: dict[str, float]


class StationRollup(BaseModel):
    station: str
    name: str
    reports: int
    max_axle: float | None


class DutyStationsResponse(BaseModel):
    duty: str
    line: str
    stations: list[StationRollup]
