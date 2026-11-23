"""R1: with several errors in the same report, the reason of the first failing check is kept.

Order: 1 form -> 2 checksum -> 3 fields -> 4 metric -> 5 station -> 6 trainset -> 7 clock -> 8 conflict
"""

from datetime import datetime, timezone

import pytest

from .conftest import make_line, outcome, submit, with_bad_checksum

FUTURE = "2031-01-01T00:00:00Z"  # invalid clock (received_at is 2026-11-03)


def q(reason):
    return ("quarantined", reason)


@pytest.mark.parametrize(
    "line, expected",
    [
        # 1 form + 2 checksum: another "$" and a wrong checksum
        (with_bad_checksum(make_line("SPD=1", serial="TS$0001")), q("malformed")),
        # 2 checksum + 3 fields: only 5 fields and a wrong checksum -> bad_checksum (previously gave malformed)
        (with_bad_checksum(make_line("SPD=1").replace(",SPD=1", "")), q("bad_checksum")),
        # 2 checksum + 4..7: everything wrong after the checksum, but the checksum fails first
        (with_bad_checksum(make_line("DOOR=1", serial="TS-0099", station="XPO", measured_at=FUTURE)), q("bad_checksum")),
        # 3 fields + 4 metric: repeated key and unknown metric
        (make_line("DOOR=1;DOOR=2"), q("malformed")),
        # 4 metric + 5 station + 6 trainset + 7 clock
        (make_line("DOOR=1", serial="TS-0099", station="XPO", measured_at=FUTURE), q("unknown_metric")),
        # 5 station + 6 trainset + 7 clock
        (make_line("SPD=1", serial="TS-0099", station="XPO", measured_at=FUTURE), q("unknown_station")),
        # 6 trainset + 7 clock
        (make_line("SPD=1", serial="TS-0099", measured_at=FUTURE), q("unknown_trainset")),
        # 7 clock alone
        (make_line("SPD=1", measured_at=FUTURE), q("clock_invalid")),
    ],
    ids=[
        "form+checksum", "checksum+fields", "checksum+everything", "fields+metric",
        "metric+station+trainset+clock", "station+trainset+clock", "trainset+clock", "clock",
    ],
)
def test_first_failing_check_gives_the_reason(line, expected):
    (report,) = submit(line)
    assert outcome(report) == expected


def test_clock_is_checked_before_conflict():
    """7 clock + 8 conflict: a report with the same identity and different content,
    but with an invalid clock, becomes clock_invalid and does not put the identity in conflict."""
    (applied,) = submit(make_line("SPD=20"))  # received_at 2026-11-03, measured 2026-11-02T08:00 -> valid
    # received before the measurement hour - 10 min -> measured_at > received_at + 10 min
    (late,) = submit(make_line("SPD=25"), received_at=datetime(2026, 11, 2, 7, 0, tzinfo=timezone.utc))
    assert outcome(late) == q("clock_invalid")
    assert outcome(applied) == ("applied", None)  # the applied one is not affected
