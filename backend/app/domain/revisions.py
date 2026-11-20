from collections.abc import Hashable, Iterable
from dataclasses import dataclass
from decimal import Decimal
from enum import Enum

Metrics = dict[str, Decimal | None]  # None = métrica removida ("-")


@dataclass(frozen=True)
class RevisionContent:
    """Conteúdo de um relatório que é comparado em R2/R4: estação + métricas."""

    station: Hashable | None
    metrics: Metrics


class RevisionOutcome(Enum):
    NEW = "new"              # primeira revisão com esta identidade -> aplicar
    DUPLICATE = "duplicate"  # igual às que já existem -> não muda nada (R2)
    CONFLICT = "conflict"    # mesma identidade, conteúdo diferente (R4)


def same_content(a: RevisionContent, b: RevisionContent) -> bool:
    """Mesma estação e mesmas métricas, com os valores comparados como números.

    Decimal compara pelo valor: Decimal("11.6") == Decimal("11.60").
    Chaves diferentes (uma métrica a mais ou a menos) = conteúdo diferente.
    """
    return a.station == b.station and a.metrics == b.metrics


def classify_revision(
    new: RevisionContent,
    existing: Iterable[RevisionContent],
    identity_in_conflict: bool,
) -> RevisionOutcome:
    """Decide o que fazer com um relatório válido, dadas as revisões já guardadas
    com a mesma identidade (serial, measured_at, rev).

    Uma identidade em conflito continua em conflito: um novo relatório com essa
    identidade é sempre CONFLICT, mesmo que seja igual a uma das versões.
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
    """Estado de uma medição (R3): revisões aplicadas por ordem crescente de rev.

    - um número define a métrica, "-" (None) remove-a, uma chave ausente mantém-na;
    - a estação vem da revisão com o rev mais alto;
    - não depende da ordem de chegada (ordena por rev).

    Métricas vazias no resultado = a medição não deve aparecer.
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
