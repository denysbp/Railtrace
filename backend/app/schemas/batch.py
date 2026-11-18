from pydantic import BaseModel


class BatchResponse(BaseModel):
    batch_id: int


class BatchStatsResponse(BaseModel):
    batch_id: int
    lines: int
    applied: int
    duplicate: int
    pending: int
    quarantined: dict[str, int]
