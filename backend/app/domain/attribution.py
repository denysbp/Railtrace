"""Rule R5 (attribution). Pure functions, no DB."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class AssignmentPeriod:

    duty_id: int
    started_at: datetime
    ended_at: datetime

    def covers(self, instant: datetime) -> bool:
        # start inclusive, end exclusive
        return self.started_at <= instant < self.ended_at


def find_duty(measured_at: datetime, assignments: Iterable[AssignmentPeriod]) -> int | None:
    for assignment in assignments:
        if assignment.covers(measured_at):
            return assignment.duty_id
    return None
