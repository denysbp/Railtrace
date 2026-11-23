from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal



class AggregationStrategy(ABC):
    """How the values of a metric are aggregated in an hour or over an entire duty."""

    @abstractmethod
    def aggregate(self, values: list[Decimal]) -> Decimal:
        """values is never empty."""


class MeanStrategy(AggregationStrategy):
    def aggregate(self, values: list[Decimal]) -> Decimal:
        return sum(values) / len(values)


class SumStrategy(AggregationStrategy):
    def aggregate(self, values: list[Decimal]) -> Decimal:
        return sum(values)


class MaxStrategy(AggregationStrategy):
    def aggregate(self, values: list[Decimal]) -> Decimal:
        return max(values)


METRIC_STRATEGIES: dict[str, AggregationStrategy] = {
    "SPD": MeanStrategy(),
    "KWH": SumStrategy(),
    **{f"AX{axle}": MaxStrategy() for axle in range(1, 9)},
}

# Axle metrics (AX*): used at most once per station
AXLE_METRICS = frozenset(metric for metric in METRIC_STRATEGIES if metric.startswith("AX"))


def strategy_for(metric: str) -> AggregationStrategy:
    return METRIC_STRATEGIES[metric]


SLOTS_PER_HOUR = 12  # one report every 5 minutes
VALUE_PLACES = Decimal("0.01")
COVERAGE_PLACES = Decimal("0.001")


def round_value(value: Decimal) -> Decimal:
    return value.quantize(VALUE_PLACES, rounding=ROUND_HALF_UP)


def coverage(count: int) -> Decimal:
    """min(count / 12, 1), with 3 decimal places."""
    return min(
        Decimal(count) / SLOTS_PER_HOUR, Decimal(1)
    ).quantize(COVERAGE_PLACES, rounding=ROUND_HALF_UP)


def utc_hour(instant: datetime) -> datetime:
    """Start of the UTC hour the instant belongs to (timezones converted to UTC)."""
    return instant.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class MetricPoint:
    """A metric value in a measurement."""

    measured_at: datetime
    metric: str
    value: Decimal


@dataclass(frozen=True)
class HourlyRollup:
    metric: str
    hour: datetime
    count: int
    value: Decimal
    coverage: Decimal


@dataclass(frozen=True)
class MetricSummary:
    metric: str
    count: int
    value: Decimal


def _aggregate(metric: str, values: list[Decimal]) -> Decimal:
    return round_value(strategy_for(metric).aggregate(values))


def hourly_rollups(points: Iterable[MetricPoint]) -> list[HourlyRollup]:
    """Per metric and UTC hour: count, value (metric strategy) and coverage."""
    groups: dict[tuple[str, datetime], list[Decimal]] = defaultdict(list)
    for point in points:
        groups[(point.metric, utc_hour(point.measured_at))].append(point.value)
    return [
        HourlyRollup(metric, hour, len(values), _aggregate(metric, values), coverage(len(values)))
        for (metric, hour), values in sorted(groups.items())
    ]


def duty_summary(points: Iterable[MetricPoint]) -> list[MetricSummary]:
    """Per metric, over the entire duty, using the same strategy as for hours."""
    groups: dict[str, list[Decimal]] = defaultdict(list)
    for point in points:
        groups[point.metric].append(point.value)
    return [
        MetricSummary(metric, len(values), _aggregate(metric, values))
        for metric, values in sorted(groups.items())
    ]


@dataclass(frozen=True)
class StationReading:
    """A measurement taken at a station, with its metrics."""

    station: int
    metrics: dict[str, Decimal]


@dataclass(frozen=True)
class StationStats:
    station: int
    reports: int
    max_axle: Decimal | None  # None = no AX* metric at that station


def station_stats(readings: Iterable[StationReading]) -> list[StationStats]:
    """Per station: number of reports and the highest AX* value."""
    counts: dict[int, int] = defaultdict(int)
    axles: dict[int, list[Decimal]] = defaultdict(list)
    for reading in readings:
        counts[reading.station] += 1
        axles[reading.station].extend(
            value for metric, value in reading.metrics.items() if metric in AXLE_METRICS
        )
    return [
        StationStats(
            station,
            counts[station],
            max(axles[station]) if axles[station] else None,
        )
        for station in sorted(counts)
    ]
