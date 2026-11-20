from time import sleep
from sqlalchemy.orm import Session
from sqlalchemy import (
    Select
)
from app.db.session import get_db
from app.models import (
    ReportRaw,
    ReportStatus
)

class Worker:
    def __init__(self):
        self.base = 1

    def _get_report(self) -> ReportRaw | None:
        query = (
            Select(ReportRaw).where(
                ReportRaw.status == ReportStatus.PENDING
            ).with_for_update(skip_locked=True).limit(1)
        )
        db = next(get_db())
        return db.scalar(query)

    def run(self):
        while True:
            report = self._get_report()
            db = next(get_db())
            if report:
                print(f"Processing {report}", flush=True)
            print("DAM")
            db.close()
            sleep(1)

if __name__ == "__main__":
    worker = Worker()
    worker.run()