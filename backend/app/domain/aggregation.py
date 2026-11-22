from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import ROUND_HALF_UP, Decimal



class AggregationStrategy(ABC):
    """Como se agregam os valores de uma métrica numa hora ou numa duty inteira."""

    @abstractmethod
    def aggregate(self, values: list[Decimal]) -> Decimal:
        """values nunca vem vazio."""


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

# Métricas de eixo (AX*): usadas no máximo por estação
AXLE_METRICS = frozenset(metric for metric in METRIC_STRATEGIES if metric.startswith("AX"))


def strategy_for(metric: str) -> AggregationStrategy:
    return METRIC_STRATEGIES[metric]


SLOTS_PER_HOUR = 12  # um relatório a cada 5 minutos
VALUE_PLACES = Decimal("0.01")
COVERAGE_PLACES = Decimal("0.001")


def round_value(value: Decimal) -> Decimal:
    return value.quantize(VALUE_PLACES, rounding=ROUND_HALF_UP)


def coverage(count: int) -> Decimal:
    """min(count / 12, 1), com 3 casas decimais."""
    return min(
        Decimal(count) / SLOTS_PER_HOUR, Decimal(1)
    ).quantize(COVERAGE_PLACES, rounding=ROUND_HALF_UP)


def utc_hour(instant: datetime) -> datetime:
    """Início da hora UTC a que pertence o instante (fusos convertidos para UTC)."""
    return instant.astimezone(timezone.utc).replace(minute=0, second=0, microsecond=0)


@dataclass(frozen=True)
class MetricPoint:
    """Um valor de uma métrica numa medição."""

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
    """Por métrica e hora UTC: count, value (estratégia da métrica) e coverage."""
    groups: dict[tuple[str, datetime], list[Decimal]] = defaultdict(list)
    for point in points:
        groups[(point.metric, utc_hour(point.measured_at))].append(point.value)
    return [
        HourlyRollup(metric, hour, len(values), _aggregate(metric, values), coverage(len(values)))
        for (metric, hour), values in sorted(groups.items())
    ]


def duty_summary(points: Iterable[MetricPoint]) -> list[MetricSummary]:
    """Por métrica, sobre a duty inteira, com a mesma estratégia das horas."""
    groups: dict[str, list[Decimal]] = defaultdict(list)
    for point in points:
        groups[point.metric].append(point.value)
    return [
        MetricSummary(metric, len(values), _aggregate(metric, values))
        for metric, values in sorted(groups.items())
    ]


@dataclass(frozen=True)
class StationReading:
    """Uma medição feita numa estação, com as suas métricas."""

    station: int
    metrics: dict[str, Decimal]


@dataclass(frozen=True)
class StationStats:
    station: int
    reports: int
    max_axle: Decimal | None  # None = nenhuma métrica AX* nessa estação


def station_stats(readings: Iterable[StationReading]) -> list[StationStats]:
    """Por estação: número de relatórios e o maior valor AX*."""
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
