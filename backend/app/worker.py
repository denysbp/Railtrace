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
                    # Avança sempre, mesmo se falhar
                    # um relatório com erro não bloqueia os seguintes
                    self.last_id = report_id
                    if process_report(report, db):
                        print(report_id, report.status)
                    else:
                        print(report_id, "falhou: fica pending e é tentado na próxima passagem")
            if report is None:
                # Fim da fila:
                # volta ao início para apanhar os pending que falharam.
                self.last_id = 0
                sleep(1)


if __name__ == "__main__":
    worker = Worker()
    worker.run()
