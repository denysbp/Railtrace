from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.domain import (
    AXLE_METRICS,
    METRIC_STRATEGIES,
    AggregationStrategy,
    MaxStrategy,
    MeanStrategy,
    MetricPoint,
    StationReading,
    SumStrategy,
    coverage,
    duty_summary,
    hourly_rollups,
    round_value,
    station_stats,
    strategy_for,
    utc_hour,
)
from app.domain.validation import KNOWN_METRICS

D = Decimal
UTC = timezone.utc


def at(hour, minute=0):
    return datetime(2026, 11, 2, hour, minute, tzinfo=UTC)


def points(metric, values, start=at(7)):
    """Um valor a cada 5 minutos a partir de start."""
    return [MetricPoint(start + timedelta(minutes=5 * i), metric, D(v)) for i, v in enumerate(values)]


# --- Estratégias (A5) ----------------------------------------------------------

def test_each_metric_kind_has_its_strategy():
    assert isinstance(strategy_for("SPD"), MeanStrategy)
    assert isinstance(strategy_for("KWH"), SumStrategy)
    for axle in ("AX1", "AX4", "AX8"):
        assert isinstance(strategy_for(axle), MaxStrategy)


def test_strategies():
    values = [D("10"), D("20"), D("33")]
    assert MeanStrategy().aggregate(values) == D("21")
    assert SumStrategy().aggregate(values) == D("63")
    assert MaxStrategy().aggregate(values) == D("33")


def test_known_metrics_come_from_the_strategy_registry():
    # um só registo: uma métrica com estratégia é conhecida em R1 e agregável em R7
    assert KNOWN_METRICS == frozenset(METRIC_STRATEGIES)
    assert AXLE_METRICS == {f"AX{i}" for i in range(1, 9)}


def test_new_metric_needs_only_a_registry_entry(monkeypatch):
    class MinStrategy(AggregationStrategy):
        def aggregate(self, values):
            return min(values)

    monkeypatch.setitem(METRIC_STRATEGIES, "TMP", MinStrategy())
    (summary,) = duty_summary(points("TMP", ["21.5", "19.25", "20"]))
    assert summary.value == D("19.25")  # 19.25 já tem 2 casas


# --- Arredondamentos e coverage ---------------------------------------------------

@pytest.mark.parametrize("count, expected", [(1, "0.083"), (6, "0.500"), (7, "0.583"), (11, "0.917"), (12, "1.000"), (13, "1.000")])
def test_coverage_is_min_count_over_12_with_3_decimals(count, expected):
    assert coverage(count) == D(expected)
    assert str(coverage(count)) == expected


def test_values_are_rounded_to_2_decimals_half_up():
    assert round_value(D("26.185")) == D("26.19")
    assert round_value(D("10") / 3) == D("3.33")
    assert round_value(D("0.005")) == D("0.01")


# --- Rollups por hora -----------------------------------------------------------

def test_hourly_spd_mean_kwh_sum_and_axle_max():
    data = points("SPD", ["10", "20", "30"]) + points("KWH", ["1.5", "2.25", "3"]) + points("AX1", ["36.1", "38.4", "37"])
    rollups = {r.metric: r for r in hourly_rollups(data)}
    assert rollups["SPD"].value == D("20.00")
    assert rollups["KWH"].value == D("6.75")
    assert rollups["AX1"].value == D("38.40")
    assert all(r.count == 3 and r.coverage == D("0.250") and r.hour == at(7) for r in rollups.values())


def test_hourly_groups_by_utc_hour_and_converts_timezones():
    lisbon = timezone(timedelta(hours=1))
    data = [
        MetricPoint(datetime(2026, 11, 2, 8, 0, tzinfo=lisbon), "SPD", D("10")),   # = 07:00Z
        MetricPoint(datetime(2026, 11, 2, 8, 59, tzinfo=lisbon), "SPD", D("20")),  # = 07:59Z
        MetricPoint(at(8), "SPD", D("40")),                                        # 08:00Z: outra hora
    ]
    rollups = hourly_rollups(data)
    assert [(r.hour, r.count, r.value) for r in rollups] == [(at(7), 2, D("15.00")), (at(8), 1, D("40.00"))]
    assert all(r.hour.tzinfo == UTC for r in rollups)
    assert utc_hour(datetime(2026, 11, 2, 0, 30, tzinfo=lisbon)) == datetime(2026, 11, 1, 23, 0, tzinfo=UTC)


def test_count_is_per_metric_when_some_measurements_lack_it():
    # 12 medições com SPD, só 6 com KWH (ex.: KWH removido por uma revisão)
    data = points("SPD", ["1"] * 12) + points("KWH", ["1"] * 6)
    rollups = {r.metric: r for r in hourly_rollups(data)}
    assert (rollups["SPD"].count, rollups["SPD"].coverage) == (12, D("1.000"))
    assert (rollups["KWH"].count, rollups["KWH"].coverage) == (6, D("0.500"))


def test_no_points_no_rollups():
    assert hourly_rollups([]) == []
    assert duty_summary([]) == []
    assert station_stats([]) == []


# --- Resumo da duty -------------------------------------------------------------

def test_summary_uses_same_strategy_over_whole_duty():
    data = points("SPD", ["10", "20"], at(7)) + points("SPD", ["40"], at(9)) + points("KWH", ["1.111", "2.222"], at(7))
    summary = {s.metric: s for s in duty_summary(data)}
    assert (summary["SPD"].count, summary["SPD"].value) == (3, D("23.33"))
    assert (summary["KWH"].count, summary["KWH"].value) == (2, D("3.33"))


# --- Por estação ----------------------------------------------------------------

def test_station_stats_count_reports_and_max_axle():
    readings = [
        StationReading(1, {"SPD": D("10"), "AX1": D("36.1"), "AX4": D("58.3")}),
        StationReading(1, {"SPD": D("12"), "AX2": D("40")}),
        StationReading(2, {"SPD": D("5")}),  # sem AX*
    ]
    stats = {s.station: s for s in station_stats(readings)}
    assert (stats[1].reports, stats[1].max_axle) == (2, D("58.3"))
    assert (stats[2].reports, stats[2].max_axle) == (1, None)
