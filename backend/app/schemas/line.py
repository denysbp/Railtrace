from pydantic import BaseModel, ConfigDict, Field


class LineCreate(BaseModel):
    code: str = Field(min_length=2, max_length=2, examples=["AZ"])
    name: str = Field(min_length=1, max_length=100, examples=["Linha Azul"])


class LineResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    code: str
    name: str
