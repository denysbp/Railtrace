from dataclasses import dataclass
from sqlalchemy import select
from app.db.session import SessionLocal
from app.models import QuarantineReason, ReportRaw, ReportStatus
from app.services.locks import lock_read_models_shared
from app.services.process_report import apply_rules


@dataclass(frozen=True)
class ReplayResult:
    report_id: int
    before: QuarantineReason
    status: ReportStatus
    reason: QuarantineReason | None

    @property
    def changed(self) -> bool:
        return self.status != ReportStatus.QUARANTINED or self.reason != self.before


def replay_quarantine(reason: QuarantineReason, dry_run: bool = False) -> list[ReplayResult]:
    with SessionLocal() as db:
        report_ids = db.scalars(
            select(ReportRaw.id)
            .where(ReportRaw.status == ReportStatus.QUARANTINED, ReportRaw.quarantine_reason == reason)
            .order_by(ReportRaw.id)
        ).all()

    if dry_run:
        with SessionLocal() as db:
            try:
                lock_read_models_shared(db)
                return [r for rid in report_ids if (r := _replay_one(db, rid, reason)) is not None]
            finally:
                db.rollback()

    results = []
    for report_id in report_ids:
        with SessionLocal() as db:
            try:
                lock_read_models_shared(db)
                result = _replay_one(db, report_id, reason)
                db.commit()
            except Exception:
                db.rollback()
                raise
        if result is not None:
            results.append(result)
    return results


def _replay_one(db, report_id: int, reason: QuarantineReason) -> ReplayResult | None:
    report = db.scalar(select(ReportRaw).where(ReportRaw.id == report_id).with_for_update())
    # Pode ter mudado desde a listagem (ex.: outro replay): só repete se ainda estiver igual
    if report.status != ReportStatus.QUARANTINED or report.quarantine_reason != reason:
        return None
    apply_rules(report, db)
    db.flush()
    return ReplayResult(report_id, reason, report.status, report.quarantine_reason)
