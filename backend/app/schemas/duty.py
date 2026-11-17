from pydantic import AwareDatetime, BaseModel, ConfigDict


class DutyResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    line_id: int
    planned_start: AwareDatetime
    planned_end: AwareDatetime
