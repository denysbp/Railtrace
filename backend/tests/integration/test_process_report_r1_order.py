"""R1: com vários erros no mesmo relatório, fica o motivo da primeira verificação que falha.

Ordem: 1 forma -> 2 checksum -> 3 campos -> 4 métrica -> 5 estação -> 6 composição -> 7 clock -> 8 conflito
"""

from datetime import datetime, timezone

import pytest

from .conftest import make_line, outcome, submit, with_bad_checksum

FUTURE = "2031-01-01T00:00:00Z"  # clock inválido (received_at é 2026-11-03)


def q(reason):
    return ("quarantined", reason)


@pytest.mark.parametrize(
    "line, expected",
    [
        # 1 forma + 2 checksum: outro "$" e checksum errado
        (with_bad_checksum(make_line("SPD=1", serial="TS$0001")), q("malformed")),
        # 2 checksum + 3 campos: só 5 campos e checksum errado -> bad_checksum (antes dava malformed)
        (with_bad_checksum(make_line("SPD=1").replace(",SPD=1", "")), q("bad_checksum")),
        # 2 checksum + 4..7: tudo errado depois do checksum, mas o checksum falha primeiro
        (with_bad_checksum(make_line("DOOR=1", serial="TS-0099", station="XPO", measured_at=FUTURE)), q("bad_checksum")),
        # 3 campos + 4 métrica: chave repetida e métrica desconhecida
        (make_line("DOOR=1;DOOR=2"), q("malformed")),
        # 4 métrica + 5 estação + 6 composição + 7 clock
        (make_line("DOOR=1", serial="TS-0099", station="XPO", measured_at=FUTURE), q("unknown_metric")),
        # 5 estação + 6 composição + 7 clock
        (make_line("SPD=1", serial="TS-0099", station="XPO", measured_at=FUTURE), q("unknown_station")),
        # 6 composição + 7 clock
        (make_line("SPD=1", serial="TS-0099", measured_at=FUTURE), q("unknown_trainset")),
        # 7 clock sozinho
        (make_line("SPD=1", measured_at=FUTURE), q("clock_invalid")),
    ],
    ids=[
        "form+checksum", "checksum+fields", "checksum+everything", "fields+metric",
        "metric+station+trainset+clock", "station+trainset+clock", "trainset+clock", "clock",
    ],
)
def test_first_failing_check_gives_the_reason(line, expected):
    (report,) = submit(line)
    assert outcome(report) == expected


def test_clock_is_checked_before_conflict():
    """7 clock + 8 conflito: um relatório com a mesma identidade e conteúdo diferente,
    mas com clock inválido, fica clock_invalid e não põe a identidade em conflito."""
    (applied,) = submit(make_line("SPD=20"))  # received_at 2026-11-03, measured 2026-11-02T08:00 -> válido
    # recebido antes da hora da medição - 10 min -> measured_at > received_at + 10 min
    (late,) = submit(make_line("SPD=25"), received_at=datetime(2026, 11, 2, 7, 0, tzinfo=timezone.utc))
    assert outcome(late) == q("clock_invalid")
    assert outcome(applied) == ("applied", None)  # o aplicado não é afetado
