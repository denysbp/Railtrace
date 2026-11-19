from pydantic import BaseModel, ConfigDict, Field


class TrainsetCreate(BaseModel):
    serial: str = Field(min_length=1, max_length=20, examples=["TS-0001"])
    home_line_code: str


class TrainsetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    serial: str
    home_line_id: int
