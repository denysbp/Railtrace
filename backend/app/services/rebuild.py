from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session
from app.models import (
    DutyHourlyRollup,
    DutyMetricSummary,
    DutyStationStats,
    Measurement,
    ReportOutcome,
    ReportRaw,
    ReportRevision,
    ReportStatus,
)
from app.services.locks import lock_read_models_exclusive
from app.services.process_report import apply_rules
from app.services.rollups import DEFERRED_KEY, defer_rollups, flush_deferred_rollups

DERIVED_TABLES = (
    DutyHourlyRollup,
    DutyMetricSummary,
    DutyStationStats,
    ReportOutcome,
    Measurement,
    ReportRevision,
)


def rebuild_read_models(db: Session) -> dict[str, int]:
    """Apaga os read models e volta a processar todos os relatórios, por ordem de chegada.

    - Numa só transação: se falhar a meio, fica tudo como estava, e a API continua a
      responder com os dados antigos até ao commit.
    - Por ordem de id (chegada): a R2 decide qual de dois relatórios iguais é o
      aplicado e qual é o duplicado, e esta ordem dá o mesmo resultado que o Worker.
    - Lock exclusivo: o Worker e o replay esperam até ao fim (a ingestão não é bloqueada).

    Os relatórios originais (raw_content, received_at, origem) não são alterados; só o
    estado da fila (status) volta a pending antes de cada relatório ser processado outra vez.
    """
    try:
        lock_read_models_exclusive(db)
        for model in DERIVED_TABLES:
            db.execute(delete(model))
        db.execute(update(ReportRaw).values(status=ReportStatus.PENDING, quarantine_reason=None))
        db.expire_all()  # os objetos carregados a seguir veem os valores acabados de repor

        report_ids = db.scalars(select(ReportRaw.id).order_by(ReportRaw.id)).all()
        # Os rollups de cada duty são calculados uma vez no fim, não a cada relatório
        defer_rollups(db)
        for report_id in report_ids:
            apply_rules(db.get(ReportRaw, report_id), db)
            db.flush()
        flush_deferred_rollups(db)

        counts = {
            "reports": len(report_ids),
            "measurements": db.scalar(select(func.count()).select_from(Measurement)),
        }
        db.commit()
        return counts
    except Exception:
        db.info.pop(DEFERRED_KEY, None)
        db.rollback()
        raise
