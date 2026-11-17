from enum import Enum


class ReportStatus(str, Enum):
    """Estado de processamento de um relatório original."""

    PENDING = "pending"
    APPLIED = "applied"
    DUPLICATE = "duplicate"
    QUARANTINED = "quarantined"
    CONFLICT = "conflict"


class QuarantineReason(str, Enum):
    """Motivo pelo qual um relatório foi colocado em quarentena.

    Só tem significado quando o status é ReportStatus.QUARANTINED.
    """

    MALFORMED = "malformed"
    BAD_CHECKSUM = "bad_checksum"
    CLOCK_INVALID = "clock_invalid"
    UNKNOWN_TRAINSET = "unknown_trainset"
    UNKNOWN_STATION = "unknown_station"
    UNKNOWN_METRIC = "unknown_metric"
