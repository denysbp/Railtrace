from time import sleep
from sqlalchemy.orm import Session
from sqlalchemy import (
    Select
)
from app.db.session import SessionLocal
from app.models import (
    ReportRaw,
    ReportStatus
)
from app.services import process_report


class Worker:
    def __init__(self):
        self.last_id = 0

    def _get_report(self, db: Session) -> ReportRaw | None:
        query = (
            Select(ReportRaw).where(
                ReportRaw.status == ReportStatus.PENDING,
                ReportRaw.id > self.last_id,
            )
            .order_by(ReportRaw.id)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        return db.scalar(query)

    def run(self):
        while True:
            with SessionLocal() as db:
                report = self._get_report(db)
                if report is not None:
                    report_id = report.id
                    # Always advance, even on failure
                    # a failed report does not block the following ones
                    self.last_id = report_id
                    if process_report(report, db):
                        print(report_id, report.status)
                    else:
                        print(report_id, "failed: stays pending and will be tried on the next pass")
            if report is None:
                # End of queue:
                # go back to the start to pick up the pending ones that failed.
                self.last_id = 0
                sleep(1)


if __name__ == "__main__":
    worker = Worker()
    worker.run()
