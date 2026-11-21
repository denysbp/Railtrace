import traceback
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session, selectinload
from app.models import (
    Measurement,
    MeasurementMetric,
    ReportOutcome,
    ReportRaw,
    ReportRevision,
    ReportRevisionMetric,
    Station,
    Trainset,
)
from app.domain import (
    Revision,
    RevisionContent,
    RevisionOutcome,
    apply_revisions,
    check_sum_valid,
    classify_revision,
    find_duty,
    has_unknown_metric,
    is_clock_invalid,
    is_malformated_fields,
    is_malformated_form,
    parse_report,
)
from app.models import ReportStatus, QuarantineReason
from app.services.attribution import assignment_periods
from app.services.locks import lock_read_models_shared
from app.services.rollups import refresh_rollups


def _set_outcome(
    db: Session,
    report: ReportRaw,
    status: ReportStatus,
    reason: QuarantineReason | None = None,
) -> None:
    """Grava o resultado de um relatório: o status em reports_raw (tira-o da fila)
    e o read model report_outcomes (o que os endpoints leem, A2).

    Sem commit: o commit é feito uma vez no fim de process_report (A3).
    Upsert porque a R4 pode mudar um relatório já processado para conflict.
    """
    report.status = status
    report.quarantine_reason = reason
    values = {
        "report_raw_id": report.id,
        "batch_id": report.batch_id,
        "batch_line": report.batch_line,
        "status": status,
        "quarantine_reason": reason,
        "raw_line": report.raw_content,
        "received_at": report.received_at,
    }
    db.execute(
        insert(ReportOutcome)
        .values(values)
        .on_conflict_do_update(
            index_elements=[ReportOutcome.report_raw_id],
            set_={"status": status, "quarantine_reason": reason},
        )
    )


def _quarantine(
    db: Session,
    report: ReportRaw,
    reason: QuarantineReason,
) -> None:
    _set_outcome(db, report, ReportStatus.QUARANTINED, reason)


def process_report(report: ReportRaw, db: Session) -> bool:
    """Aplica as regras a um relatório numa só transação.

    Devolve False em caso de erro técnico: faz rollback e o relatório continua
    pending, para ser tentado outra vez (ver Worker).
    """
    try:
        lock_read_models_shared(db)  # espera se um rebuild (A4) estiver a correr
        apply_rules(report, db)
        db.commit()
        return True
    except Exception:
        db.rollback()
        traceback.print_exc()  # não esconder o erro
        return False


def apply_rules(report: ReportRaw, db: Session) -> None:
    """Aplica R1–R5 e R7 a um relatório, sem commit (quem chama gere a transação).

    R1: verificações pela ordem do desafio; a primeira que falha dá o motivo.
    """
    text = report.raw_content
    # 1. Forma $...*hh, sem outro $ nem *
    if is_malformated_form(text):
        _quarantine(db, report, QuarantineReason.MALFORMED)
        return
    # 2. Checksum
    if not check_sum_valid(text):
        _quarantine(db, report, QuarantineReason.BAD_CHECKSUM)
        return
    # 3. 6 campos, tipo TRN, cada campo válido, sem chaves repetidas, ≥ 1 métrica
    if is_malformated_fields(text):
        _quarantine(db, report, QuarantineReason.MALFORMED)
        return
    parsed = parse_report(text)
    # 4. Todas as chaves de métrica conhecidas
    if has_unknown_metric(text[1:].split("*")[0].split(",")[5]):
        _quarantine(db, report, QuarantineReason.UNKNOWN_METRIC)
        return
    # 5. Estação "-" ou conhecida (None = "-")
    station_id = None
    if parsed.station is not None:
        station_id = db.scalar(select(Station.id).where(Station.code == parsed.station))
        if station_id is None:
            _quarantine(db, report, QuarantineReason.UNKNOWN_STATION)
            return
    # 6. Composição registada
    trainset_id = db.scalar(select(Trainset.id).where(Trainset.serial == parsed.serial))
    if trainset_id is None:
        _quarantine(db, report, QuarantineReason.UNKNOWN_TRAINSET)
        return
    # 7. Clock: received_at = quando a API gravou o relatório, não quando o Worker o processa
    if is_clock_invalid(parsed.measured_at, report.received_at):
        _quarantine(db, report, QuarantineReason.CLOCK_INVALID)
        return
    # 8. Conflito (R4), dentro de _apply_revision
    measured_at = datetime.fromisoformat(parsed.measured_at)  # válido: passou is_clock_invalid
    _apply_revision(report, db, trainset_id, measured_at, parsed.rev, station_id, parsed.metrics)


def _apply_revision(report, db, trainset_id, measured_at, rev, station_id, metrics) -> None:
    """R2 + R4: compara com as revisões já guardadas com a mesma identidade."""
    # Revisões com a mesma identidade (serial, measured_at, rev) e o estado dos seus relatórios
    existing = db.scalars(
        select(ReportRevision)
        .where(
            ReportRevision.trainset_id == trainset_id,
            ReportRevision.measured_at == measured_at,
            ReportRevision.rev == rev,
        )
        .options(selectinload(ReportRevision.metrics), selectinload(ReportRevision.report_raw))
    ).all()
    # Num replay (R8) o relatório pode já ter a sua revisão: não conta como "outra"
    already_stored = any(other.report_raw_id == report.id for other in existing)
    existing = [other for other in existing if other.report_raw_id != report.id]
    identity_in_conflict = any(
        other.report_raw.quarantine_reason == QuarantineReason.CONFLICT for other in existing
    )
    new_content = RevisionContent(station=station_id, metrics=metrics)
    outcome = classify_revision(
        new_content,
        [_content(other) for other in existing],
        identity_in_conflict,
    )

    # Guarda sempre a revisão (também duplicados e conflitos): é o registo da identidade
    # deste relatório, necessário para que um conflito posterior o encontre (R4).
    if not already_stored:
        db.add(
            ReportRevision(
                report_raw_id=report.id,
                trainset_id=trainset_id,
                measured_at=measured_at,
                rev=rev,
                station_id=station_id,
                metrics=[ReportRevisionMetric(metric=name, value=value) for name, value in metrics.items()],
            )
        )

    if outcome is RevisionOutcome.DUPLICATE:
        _set_outcome(db, report, ReportStatus.DUPLICATE)  # não muda a medição (R2)
        return

    if outcome is RevisionOutcome.NEW:
        _set_outcome(db, report, ReportStatus.APPLIED)
    else:
        # R4: todos os relatórios desta identidade passam a conflict, incluindo os aplicados
        _quarantine(db, report, QuarantineReason.CONFLICT)
        for other in existing:
            _quarantine(db, other.report_raw, QuarantineReason.CONFLICT)

    db.flush()
    _rebuild_measurement(db, trainset_id, measured_at)


def _content(revision: ReportRevision) -> RevisionContent:
    return RevisionContent(
        station=revision.station_id,
        metrics={metric.metric: metric.value for metric in revision.metrics},
    )


def _rebuild_measurement(db: Session, trainset_id: int, measured_at: datetime) -> None:
    """R3: o estado da medição vem só das revisões aplicadas (sem conflitos nem duplicados)."""
    applied = db.scalars(
        select(ReportRevision)
        .join(ReportRevision.report_raw)
        .where(
            ReportRevision.trainset_id == trainset_id,
            ReportRevision.measured_at == measured_at,
            ReportRaw.status == ReportStatus.APPLIED,
        )
        .options(selectinload(ReportRevision.metrics))
    ).all()
    state = apply_revisions(Revision(rev=r.rev, content=_content(r)) for r in applied)

    measurement = db.scalar(
        select(Measurement)
        .where(Measurement.trainset_id == trainset_id, Measurement.measured_at == measured_at)
        .options(selectinload(Measurement.metrics))
    )
    # Duty antes da alteração: os seus rollups também mudam se a medição sair dela (R7)
    old_duty_id = measurement.duty_id if measurement is not None else None

    if not state.metrics:
        # Sem métricas a medição não aparece (R3)
        if measurement is not None:
            db.delete(measurement)
            db.flush()
            refresh_rollups(db, [old_duty_id])
        return

    if measurement is None:
        measurement = Measurement(trainset_id=trainset_id, measured_at=measured_at)
        db.add(measurement)
    measurement.station_id = state.station
    # R5: duty do assignment desta composição que cobre measured_at (None = não atribuída)
    measurement.duty_id = find_duty(measured_at, assignment_periods(db, trainset_id))
    # Sincroniza as métricas: atualiza as que ficam, apaga as que saíram, junta as novas
    current = {metric.metric: metric for metric in measurement.metrics}
    for name, metric in current.items():
        if name in state.metrics:
            metric.value = state.metrics[name]
        else:
            measurement.metrics.remove(metric)
    for name, value in state.metrics.items():
        if name not in current:
            measurement.metrics.append(MeasurementMetric(metric=name, value=value))

    db.flush()  # os rollups são calculados a partir das medições já gravadas
    refresh_rollups(db, [old_duty_id, measurement.duty_id])
