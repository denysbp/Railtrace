from sqlalchemy import func, select
from sqlalchemy.orm import Session

READ_MODELS_LOCK = 7_000_001


def lock_read_models_shared(db: Session) -> None:
    db.execute(select(func.pg_advisory_xact_lock_shared(READ_MODELS_LOCK)))


def lock_read_models_exclusive(db: Session) -> None:
    db.execute(select(func.pg_advisory_xact_lock(READ_MODELS_LOCK)))
