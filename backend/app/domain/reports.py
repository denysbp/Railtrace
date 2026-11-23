from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class ParsedReport:
    """Fields of a $TRN report already validated by is_malformated_form and is_malformated_fields."""

    serial: str
    measured_at: str
    rev: int
    station: str | None  # None = "-" (no station)
    metrics: dict[str, Decimal | None]  # None = "-" (metric removed, R3)


def parse_report(text: str) -> ParsedReport:
    """Splits the fields of a report. Only call after is_malformated_fields."""
    _, serial, measured_at, rev, station, metrics = text[1:].split("*")[0].split(",")
    values: dict[str, Decimal | None] = {}
    for pair in metrics.split(";"):
        name, _, value = pair.partition("=")
        values[name] = None if value == "-" else Decimal(value)
    return ParsedReport(
        serial=serial,
        measured_at=measured_at,
        rev=int(rev),
        station=None if station == "-" else station,
        metrics=values,
    )
