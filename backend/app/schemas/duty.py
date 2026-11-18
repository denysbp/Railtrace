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
