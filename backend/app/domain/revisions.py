from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

Metrics = dict[str, Decimal | None]  # None = metric removed ("-")


@dataclass(frozen=True)
class RevisionContent:
    """Report content compared in R2/R4: station + metrics."""

    station: Hashable | None
    metrics: Metrics


class RevisionOutcome(Enum):
    NEW = "new"              # first revision with this identity -> apply
    DUPLICATE = "duplicate"  # same as existing ones -> changes nothing (R2)
    CONFLICT = "conflict"    # same identity, different content (R4)


def same_content(a: RevisionContent, b: RevisionContent) -> bool:
    """Same station and same metrics, with values compared as numbers.

    Decimal compares by value: Decimal("11.6") == Decimal("11.60").
    Different keys (one metric more or less) = different content.
    """
    return a.station == b.station and a.metrics == b.metrics


def classify_revision(
    new: RevisionContent,
    existing: Iterable[RevisionContent],
    identity_in_conflict: bool,
) -> RevisionOutcome:
    """Decides what to do with a valid report, given the revisions already stored
    with the same identity (serial, measured_at, rev).

    An identity in conflict stays in conflict: a new report with that
    identity is always CONFLICT, even if it matches one of the versions.
    """
    if identity_in_conflict:
        return RevisionOutcome.CONFLICT
    existing = list(existing)
    if not existing:
        return RevisionOutcome.NEW
    if all(same_content(new, other) for other in existing):
        return RevisionOutcome.DUPLICATE
    return RevisionOutcome.CONFLICT


@dataclass(frozen=True)
class Revision:
    rev: int
    content: RevisionContent


def apply_revisions(revisions: Iterable[Revision]) -> RevisionContent:
    """State of a measurement (R3): applied revisions in ascending rev order.

    - a number sets the metric, "-" (None) removes it, a missing key keeps it;
    - the station comes from the revision with the highest rev;
    - independent of arrival order (sorted by rev).

    Empty metrics in the result = the measurement must not appear.
    """
    ordered = sorted(revisions, key=lambda revision: revision.rev)
    metrics: Metrics = {}
    for revision in ordered:
        for name, value in revision.content.metrics.items():
            if value is None:
                metrics.pop(name, None)
            else:
                metrics[name] = value
    station = ordered[-1].content.station if ordered else None
    return RevisionContent(station=station, metrics=metrics)
