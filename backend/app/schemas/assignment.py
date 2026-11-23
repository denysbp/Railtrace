from typing import Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class AssignmentCreate(BaseModel):
    trainset_id: int = Field(gt=0)
    duty_id: int = Field(gt=0)
    started_at: AwareDatetime
    ended_at: AwareDatetime

    @model_validator(mode="after")
    def _check_interval(self) -> Self:
        if self.ended_at <= self.started_at:
            raise ValueError("ended_at must be after started_at")
        return self


class AssignmentUpdate(BaseModel):

    started_at: AwareDatetime | None = None
    ended_at: AwareDatetime | None = None

    @model_validator(mode="after")
    def _check_interval(self) -> Self:
        if (
            self.started_at is not None
            and self.ended_at is not None
            and self.ended_at <= self.started_at
        ):
            raise ValueError("ended_at must be after started_at")
        return self


class AssignmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    trainset_id: int
    duty_id: int
    started_at: AwareDatetime
    ended_at: AwareDatetime


class DutyAssignmentCreate(BaseModel):
    """Body of POST /duties/{code}/assignments (the duty comes from the path)."""

    trainset: str = Field(min_length=1, examples=["TS-0001"])
    started_at: AwareDatetime
    ended_at: AwareDatetime

    @model_validator(mode="after")
    def _check_interval(self) -> Self:
        if self.ended_at <= self.started_at:
            raise ValueError("ended_at must be after started_at")
        return self
