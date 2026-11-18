from enum import Enum


class ReportStatus(str, Enum):
    PENDING = "pending"
    APPLIED = "applied"
    DUPLICATE = "duplicate"
    QUARANTINED = "quarantined"
    CONFLICT = "conflict"


class QuarantineReason(str, Enum):
    MALFORMED = "malformed"
    BAD_CHECKSUM = "bad_checksum"
    CLOCK_INVALID = "clock_invalid"
    UNKNOWN_TRAINSET = "unknown_trainset"
    UNKNOWN_STATION = "unknown_station"
    UNKNOWN_METRIC = "unknown_metric"
    CONFLICT = "conflict"
