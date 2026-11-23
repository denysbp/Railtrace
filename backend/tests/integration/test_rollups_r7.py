"""R7: the rollups (hour, summary, station) follow the measurements and the assignments.

Seed, TS-0001 on 2026-11-02: AZ-D01-20261102 [07:00, 11:00) and AZ-D02-20261102 [13:00, 17:00).
"""

from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.db.session import SessionLocal
from app.main import app
from app.models import Assignment, Duty

from .conftest import make_line, submit

D = Decimal
DAY = "2026-11-02"
AZ1 = "AZ-D01-20261102"
AZ2 = "AZ-D02-20261102"
client = TestClient(app)


def at(hhmm):
    return f"{DAY}T{hhmm}:00Z"


def hourly(duty, metric):
    with SessionLocal() as db:
        rows = db.execute(text(
            "select to_char(h.hour at time zone 'UTC', 'HH24:MI'), h.count, h.value, h.coverage "
            "from duty_hourly_rollups h join duties d on d.id = h.duty_id "
            "where d.code = :duty and h.metric = :metric order by h.hour"
        ), {"duty": duty, "metric": metric}).all()
    return [tuple(row) for row in rows]


def summary(duty):
    with SessionLocal() as db:
        rows = db.execute(text(
            "select s.metric, s.count, s.value from duty_metric_summaries s "
            "join duties d on d.id = s.duty_id where d.code = :duty"
        ), {"duty": duty}).all()
    return {metric: (count, value) for metric, count, value in rows}


def stations(duty):
    with SessionLocal() as db:
        rows = db.execute(text(
            "select st.code, s.reports, s.max_axle from duty_station_stats s "
            "join duties d on d.id = s.duty_id join stations st on st.id = s.station_id where d.code = :duty"
        ), {"duty": duty}).all()
    return {code: (reports, max_axle) for code, reports, max_axle in rows}


def assignment_id(duty):
    with SessionLocal() as db:
        return db.scalar(select(Assignment.id).join(Duty).where(Duty.code == duty))


def line(hhmm, metrics, **kwargs):
    return make_line(metrics, measured_at=at(hhmm), **kwargs)


# --- creation by the Worker -------------------------------------------------------

def test_worker_creates_hourly_summary_and_station_rollups():
    submit(
        line("07:00", "SPD=10;KWH=1.5;AX1=36.1", station="REB"),
        line("07:05", "SPD=20;KWH=2.25;AX1=38.4", station="REB"),
        line("07:10", "SPD=33;KWH=3;AX1=37", station="ALF"),
    )
    assert hourly(AZ1, "SPD") == [("07:00", 3, D("21.00"), D("0.250"))]   # mean
    assert hourly(AZ1, "KWH") == [("07:00", 3, D("6.75"), D("0.250"))]    # sum
    assert hourly(AZ1, "AX1") == [("07:00", 3, D("38.40"), D("0.250"))]   # maximum
    assert summary(AZ1) == {"SPD": (3, D("21.00")), "KWH": (3, D("6.75")), "AX1": (3, D("38.40"))}
    assert stations(AZ1) == {"REB": (2, D("38.4")), "ALF": (1, D("37"))}


def test_hours_are_utc_even_when_reports_use_another_offset():
    # 08:30+01:00 = 07:30Z ; 09:05+01:00 = 08:05Z
    submit(make_line("SPD=10", measured_at=f"{DAY}T08:30:00+01:00"), make_line("SPD=30", measured_at=f"{DAY}T09:05:00+01:00"))
    assert [(h, c) for h, c, _, _ in hourly(AZ1, "SPD")] == [("07:00", 1), ("08:00", 1)]


def test_coverage_and_rounding_for_a_full_hour():
    values = ["25.1", "26.2", "27.3", "24.4", "26.5", "25.6", "27.7", "24.8", "26.9", "25.1", "26.2", "28.3"]
    submit(*(line(f"08:{5 * i:02d}", f"SPD={v}") for i, v in enumerate(values)))
    ((hour, count, value, cov),) = hourly(AZ1, "SPD")
    assert (hour, count, cov) == ("08:00", 12, D("1.000"))
    assert value == D("26.18")  # 314.1 / 12 = 26.175 -> 26.18 (round half up)


def test_unattributed_measurements_have_no_rollups():
    submit(line("12:00", "SPD=10", station="REB"))  # between duties
    assert hourly(AZ1, "SPD") == [] and summary(AZ1) == {} and stations(AZ1) == {}
    assert hourly(AZ2, "SPD") == []


# --- corrections, removals, and conflicts (R3/R4) -------------------------------

def test_correction_updates_rollups():
    submit(line("07:00", "SPD=10;KWH=1", rev=0), line("07:05", "SPD=20;KWH=1", rev=0))
    assert hourly(AZ1, "SPD") == [("07:00", 2, D("15.00"), D("0.167"))]
    submit(line("07:05", "SPD=40", rev=1))  # corrects SPD, keeps KWH
    assert hourly(AZ1, "SPD") == [("07:00", 2, D("25.00"), D("0.167"))]
    assert hourly(AZ1, "KWH") == [("07:00", 2, D("2.00"), D("0.167"))]


def test_removed_metric_leaves_the_rollups():
    submit(line("07:00", "SPD=10;AX1=36", rev=0), line("07:05", "SPD=20;AX1=39", rev=0))
    submit(line("07:05", "AX1=-", rev=1))
    assert hourly(AZ1, "AX1") == [("07:00", 1, D("36.00"), D("0.083"))]
    assert summary(AZ1)["SPD"] == (2, D("15.00"))  # the measurement remains (still has SPD)


def test_measurement_with_no_metrics_left_is_not_counted():
    submit(line("07:00", "SPD=10", rev=0, station="REB"), line("07:05", "SPD=20", rev=0, station="REB"))
    submit(line("07:05", "SPD=-", rev=1, station="REB"))  # removes the only metric
    assert hourly(AZ1, "SPD") == [("07:00", 1, D("10.00"), D("0.083"))]
    assert stations(AZ1) == {"REB": (1, None)}


def test_conflict_removes_the_disputed_values_from_rollups():
    submit(line("07:00", "SPD=10", rev=0), line("07:05", "SPD=20", rev=0))
    submit(line("07:05", "SPD=99", rev=0))  # same identity, different content
    assert hourly(AZ1, "SPD") == [("07:00", 1, D("10.00"), D("0.083"))]


# --- assignments (R5) -----------------------------------------------------------

def test_assignment_changes_move_rollups_between_duties():
    submit(line("08:00", "SPD=10"), line("09:30", "SPD=30"), line("10:00", "SPD=50"))
    assert summary(AZ1) == {"SPD": (3, D("30.00"))}

    # shortens AZ-D01 to [07:00, 09:00): 09:30 and 10:00 leave
    assert client.patch(f"/v1/assignments/{assignment_id(AZ1)}", json={"ended_at": at("09:00")}).status_code == 200
    assert summary(AZ1) == {"SPD": (1, D("10.00"))}

    # new assignment of TS-0001 on AZ-D02 in [09:00, 11:00): 09:30 and 10:00 enter AZ-D02
    response = client.post(f"/v1/duties/{AZ2}/assignments",
                           json={"trainset": "TS-0001", "started_at": at("09:00"), "ended_at": at("11:00")})
    assert response.status_code == 201
    assert summary(AZ2) == {"SPD": (2, D("40.00"))}
    assert hourly(AZ2, "SPD") == [("09:00", 1, D("30.00"), D("0.083")), ("10:00", 1, D("50.00"), D("0.083"))]
    assert summary(AZ1) == {"SPD": (1, D("10.00"))}


def test_overlapping_assignment_change_keeps_rollups():
    submit(line("10:00", "SPD=10"))
    before = (hourly(AZ1, "SPD"), summary(AZ1), summary(AZ2))
    # extending AZ-D01 until 14:00 overlaps AZ-D02 (same trainset) -> 409
    assert client.patch(f"/v1/assignments/{assignment_id(AZ1)}", json={"ended_at": at("14:00")}).status_code == 409
    assert (hourly(AZ1, "SPD"), summary(AZ1), summary(AZ2)) == before
