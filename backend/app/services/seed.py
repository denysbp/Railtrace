import json
from datetime import datetime
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models.assignment import Assignment
from app.models.duty import Duty
from app.models.line import Line
from app.models.line_station import LineStation
from app.models.station import Station
from app.models.trainset import Trainset


def load_seed(db: Session, path: Path) -> dict[str, int]:
    """
    Carrega o seed numa só transação.
    Idempotente: o que já existe não é inserido outra vez.

    Devolve quantas linhas foram inseridas em cada tabela.
    """
    with open(path, encoding="utf-8") as f:
        seed = json.load(f)

    inserted: dict[str, int] = {}
    try:
        inserted["lines"] = _insert_ignore(db, Line, [
            {
                "code": line["code"],
                "name": line["name"]
            }
            for line in seed["lines"]
        ])
        inserted["stations"] = _insert_ignore(db, Station, [
            {
                "code": station["code"],
                "name": station["name"]
            }
            for station in seed["stations"]
        ])

        line_ids = _ids_by(db, Line.code, Line.id)
        station_ids = _ids_by(db, Station.code, Station.id)

        inserted["line_stations"] = _insert_ignore(db, LineStation, [
            {
                "line_id": line_ids[line["code"]],
                "station_id": station_ids[code],
                "position": position
            }
            for line in seed["lines"]
            for position, code in enumerate(line["stations"], start=1)
        ])

        inserted["trainsets"] = _insert_ignore(db, Trainset, [
            {
                "serial": trainset["serial"],
                "home_line_id": line_ids[trainset["line"]]
            }
            for trainset in seed["trainsets"]
        ])

        inserted["duties"] = _insert_ignore(db, Duty, [
            {
                "code": duty["code"],
                "line_id": line_ids[duty["line"]],
                "planned_start": datetime.fromisoformat(duty["planned_start"]),
                "planned_end": datetime.fromisoformat(duty["planned_end"]),
            }
            for duty in seed["duties"]
        ])

        trainset_ids = _ids_by(db, Trainset.serial, Trainset.id)
        duty_ids = _ids_by(db, Duty.code, Duty.id)
        inserted["assignments"] = _insert_assignments(db, [
            {
                "trainset_id": trainset_ids[assignment["trainset"]],
                "duty_id": duty_ids[assignment["duty"]],
                "started_at": datetime.fromisoformat(assignment["started_at"]),
                "ended_at": datetime.fromisoformat(assignment["ended_at"]),
            }
            for assignment in seed["assignments"]
        ])

        db.commit()
    except Exception:
        db.rollback()
        raise

    return inserted


def _insert_ignore(db: Session, model, rows: list[dict]) -> int:
    """
    INSERT ... ON CONFLICT DO NOTHING: as linhas que já existem
    (mesma chave única) são ignoradas.
    """
    if not rows:
        return 0
    # RETURNING devolve só as linhas realmente inseridas
    pk = list(model.__table__.primary_key.columns)[0]
    result = db.execute(insert(model).values(rows).on_conflict_do_nothing().returning(pk))
    return len(result.all())


def _ids_by(db: Session, key_column, id_column) -> dict:
    return dict(db.execute(select(key_column, id_column)).all())


def _insert_assignments(db: Session, rows: list[dict]) -> int:
    inserted = 0
    for row in rows:
        # scalar procura exatamente como os msm valores
        exists = db.scalar(select(Assignment.id).filter_by(**row))
        if exists is None:
            db.add(Assignment(**row))
            db.flush() # envia as operacoes sem terminar a transacao
            inserted += 1
    return inserted
