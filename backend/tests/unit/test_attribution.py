from datetime import datetime, timezone

from app.domain import AssignmentPeriod, find_duty


def at(hour, minute=0):
    return datetime(2026, 11, 2, hour, minute, tzinfo=timezone.utc)


ASSIGNMENTS = [
    AssignmentPeriod(duty_id=1, started_at=at(7), ended_at=at(11)),
    AssignmentPeriod(duty_id=2, started_at=at(13), ended_at=at(17)),
]


def test_measurement_inside_an_assignment_belongs_to_its_duty():
    assert find_duty(at(8), ASSIGNMENTS) == 1
    assert find_duty(at(15), ASSIGNMENTS) == 2


def test_start_is_included_and_end_is_excluded():
    assert find_duty(at(7), ASSIGNMENTS) == 1      # [started_at
    assert find_duty(at(10, 59), ASSIGNMENTS) == 1
    assert find_duty(at(11), ASSIGNMENTS) is None  # ended_at)


def test_outside_every_assignment_is_unattributed():
    assert find_duty(at(6, 59), ASSIGNMENTS) is None
    assert find_duty(at(12), ASSIGNMENTS) is None  # between two duties (e.g. in the depot)
    assert find_duty(at(8), []) is None


def test_other_timezone_is_compared_as_the_same_instant():
    lisbon_plus_one = datetime.fromisoformat("2026-11-02T08:30:00+01:00")  # = 07:30Z
    assert find_duty(lisbon_plus_one, ASSIGNMENTS) == 1
