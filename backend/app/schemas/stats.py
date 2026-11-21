from pydantic import BaseModel


class StatsResponse(BaseModel):
    reports_total: int
    measurements: int
    attributed: int
    unattributed: int
    quarantined: dict[str, int]
    pending: int
