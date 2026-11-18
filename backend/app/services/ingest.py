import io
from typing import BinaryIO

from sqlalchemy.orm import Session

from app.models.batch import Batch
from app.models.report_raw import ReportRaw


def ingest_batch(db: Session, name: str, file: BinaryIO) -> int:
    batch = Batch(name=name)

    # utf-8-sig: os ficheiros do depósito começam com um BOM; sem isto a
    # primeira linha seria "﻿# depot ..." e não começaria por "#"
    text = io.TextIOWrapper(file, encoding="utf-8-sig")

    for number, line in enumerate(text, start=1):
        line = line.rstrip("\r\n")
        if not line or line.startswith("#"):
            continue
        batch.reports.append(ReportRaw(raw_content=line, batch_line=number))

    try:
        db.add(batch)
        db.commit()
    except Exception:
        db.rollback()
        raise

    return batch.id
