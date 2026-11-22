import string
from datetime import datetime, timedelta, timezone

from .aggregation import METRIC_STRATEGIES

CLOCK_MIN = datetime(2020, 1, 1, tzinfo=timezone.utc)
CLOCK_MAX_AHEAD = timedelta(minutes=10)

KNOWN_METRICS = frozenset(METRIC_STRATEGIES)


def has_unknown_metric(metrics: str) -> bool:
    return any(pair.partition("=")[0] not in KNOWN_METRICS for pair in metrics.split(";"))


def check_sum_valid(text: str) -> bool:
    if not text.startswith("$") or text.count("*") != 1:
        return False
    body, value = text[1:].split("*")
    if not value or any(c not in string.hexdigits for c in value):
        return False
    check_sum = 0
    for byte in body.encode():
        check_sum ^= byte
    return check_sum == int(value, 16)


def is_clock_invalid(measured_at: str, received_at: datetime) -> bool:
    try:
        instant = datetime.fromisoformat(measured_at)
    except ValueError:
        return True
    if instant.tzinfo is None:
        return True
    # datetimes com fuso comparam-se como instantes UTC
    return not (CLOCK_MIN <= instant <= received_at + CLOCK_MAX_AHEAD)


def is_malformated_form(text: str) -> bool:
    if not text.startswith("$") or text.count("$") != 1 or text.count("*") != 1:
        return True
    checksum = text.split("*")[1]
    # hh: exatamente 2 dígitos hexadecimais
    return len(checksum) != 2 or any(c not in string.hexdigits for c in checksum)


def is_malformated_fields(text: str) -> bool:
    fields = text[1:].split("*")[0].split(",")
    if len(fields) != 6:
        return True
    kind, serial, measured_at, rev, station, metrics = fields

    if kind != "TRN" or not serial or not station or not _is_digits(rev):
        return True

    seen = set()
    for pair in metrics.split(";"):
        name, sep, value = pair.partition("=")
        if not sep or not name or name in seen:
            return True
        seen.add(name)
        # "-" = métrica removida (R3)
        if value != "-" and not _is_number(value):
            return True

    return False


def _is_digits(value: str) -> bool:
    return value != "" and all(c in string.digits for c in value)


def _is_number(value: str) -> bool:
    """Número decimal simples: 12, 12.5, -0.3 (sem expoentes, espaços, nan/inf)."""
    whole, dot, fraction = value.removeprefix("-").partition(".")
    return _is_digits(whole) and (not dot or _is_digits(fraction))
