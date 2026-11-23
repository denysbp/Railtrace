from fastapi.testclient import TestClient

from app.main import app

from .conftest import make_line, submit, with_bad_checksum

client = TestClient(app)
AZ1 = "AZ-D01-20261102"  # TS-0001, [07:00, 11:00) on 2026-11-02, line AZ


def at(hhmm):
    return f"2026-11-02T{hhmm}:00Z"


def setup_measurements():
    submit(
        make_line("SPD=10;KWH=1.5;AX1=36.1", measured_at=at("07:00"), station="REB"),
        make_line("SPD=20;KWH=2.25;AX1=38.4", measured_at=at("07:05"), station="-"),
        make_line("SPD=33;AX4=40", measured_at=f"2026-11-02T09:10:00+01:00", station="ALF"),  # = 08:10Z
    )


def test_readings_returns_points_in_time_order():
    setup_measurements()
    body = client.get(f"/v1/duties/{AZ1}/readings", params={"metric": "SPD"}).json()
    assert body == {
        "duty": AZ1,
        "metric": "SPD",
        "points": [
            {"measured_at": "2026-11-02T07:00:00Z", "value": 10.0, "trainset": "TS-0001", "station": "REB"},
            {"measured_at": "2026-11-02T07:05:00Z", "value": 20.0, "trainset": "TS-0001", "station": None},
            {"measured_at": "2026-11-02T08:10:00Z", "value": 33.0, "trainset": "TS-0001", "station": "ALF"},
        ],
    }
    # only the measurements that have the metric
    kwh = client.get(f"/v1/duties/{AZ1}/readings", params={"metric": "KWH"}).json()["points"]
    assert [p["value"] for p in kwh] == [1.5, 2.25]


def test_hourly_returns_utc_buckets():
    setup_measurements()
    body = client.get(f"/v1/duties/{AZ1}/hourly", params={"metric": "SPD"}).json()
    assert body == {
        "duty": AZ1,
        "metric": "SPD",
        "buckets": [
            {"hour": "2026-11-02T07:00:00Z", "count": 2, "value": 15.0, "coverage": 0.167},
            {"hour": "2026-11-02T08:00:00Z", "count": 1, "value": 33.0, "coverage": 0.083},
        ],
    }


def test_summary_returns_trainsets_measurements_and_metrics():
    setup_measurements()
    body = client.get(f"/v1/duties/{AZ1}/summary").json()
    assert body == {
        "duty": AZ1,
        "trainsets": ["TS-0001"],
        "measurements": 3,
        "metrics": {"SPD": 21.0, "KWH": 3.75, "AX1": 38.4, "AX4": 40.0},
    }
    assert list(body["metrics"]) == ["SPD", "KWH", "AX1", "AX4"]  # registration order


def test_stations_lists_every_station_of_the_line_in_order():
    setup_measurements()
    body = client.get(f"/v1/duties/{AZ1}/stations").json()
    assert body["duty"] == AZ1 and body["line"] == "AZ"
    stations = body["stations"]
    assert len(stations) == 18  # all stations of line AZ
    assert stations[0] == {"station": "REB", "name": "Reboleira", "reports": 1, "max_axle": 36.1}
    assert stations[1]["station"] == "AMD" and stations[1]["reports"] == 0 and stations[1]["max_axle"] is None
    assert stations[2] == {"station": "ALF", "name": "Alfornelos", "reports": 1, "max_axle": 40.0}


def test_empty_duty_has_empty_read_models():
    assert client.get(f"/v1/duties/{AZ1}/readings", params={"metric": "SPD"}).json()["points"] == []
    assert client.get(f"/v1/duties/{AZ1}/hourly", params={"metric": "SPD"}).json()["buckets"] == []
    assert client.get(f"/v1/duties/{AZ1}/summary").json() == {"duty": AZ1, "trainsets": [], "measurements": 0, "metrics": {}}
    assert all(s["reports"] == 0 for s in client.get(f"/v1/duties/{AZ1}/stations").json()["stations"])


def test_errors():
    for path in ("readings?metric=SPD", "hourly?metric=SPD", "summary", "stations"):
        assert client.get(f"/v1/duties/NAO-EXISTE/{path}").status_code == 404
    assert client.get(f"/v1/duties/{AZ1}/readings", params={"metric": "DOOR"}).status_code == 422
    assert client.get(f"/v1/duties/{AZ1}/hourly", params={"metric": "DOOR"}).status_code == 422
    assert client.get(f"/v1/duties/{AZ1}/readings").status_code == 422  # metric is required


def test_stats_counts_reports_and_measurements():
    setup_measurements()  # 3 applied and attributed
    submit(
        make_line("SPD=1", measured_at=at("12:00")),            # applied, unattributed
        with_bad_checksum(make_line("SPD=1", measured_at=at("12:05"))),  # bad_checksum
        make_line("SPD=1", measured_at=at("12:10"), serial="TS-0099"),   # unknown_trainset
    )
    assert client.get("/v1/stats").json() == {
        "reports_total": 6,
        "measurements": 4,
        "attributed": 3,
        "unattributed": 1,
        "quarantined": {"bad_checksum": 1, "unknown_trainset": 1},
        "pending": 0,
    }
