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
    """Deletes the read models and reprocesses all reports, in arrival order.

    - Single transaction: if it fails halfway, everything is left as it was, and the API keeps
      responding with the old data until the commit.
    - By id order (arrival): R2 decides which of two identical reports is
      applied and which is the duplicate, and this order gives the same result as the Worker.
    - Exclusive lock: the Worker and replay wait until it finishes (ingestion is not blocked).

    The original reports (raw_content, received_at, source) are not changed; only the
    queue state (status) goes back to pending before each report is processed again.
    """
    try:
        lock_read_models_exclusive(db)
        for model in DERIVED_TABLES:
            db.execute(delete(model))
        db.execute(update(ReportRaw).values(status=ReportStatus.PENDING, quarantine_reason=None))
        db.expire_all()  # objects loaded afterwards see the freshly restored values

        report_ids = db.scalars(select(ReportRaw.id).order_by(ReportRaw.id)).all()
        # Each duty's rollups are computed once at the end, not per report
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
