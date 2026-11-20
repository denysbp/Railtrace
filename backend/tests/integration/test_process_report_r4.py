"""R2 (duplicados), R3 (revisões) e R4 (conflitos) no process_report, contra a BD de testes."""

import importlib
from decimal import Decimal

import pytest

# O módulo (não a função process_report que services/__init__.py reexporta com o mesmo nome)
process_report_module = importlib.import_module("app.services.process_report")

from .conftest import make_line, measurement, outcome, revisions_count, submit

APPLIED = ("applied", None)
DUPLICATE = ("duplicate", None)
CONFLICT = ("quarantined", "conflict")


def test_1_first_revision_is_applied_and_creates_measurement():
    (report,) = submit(make_line("SPD=20.0;KWH=1.5"))
    assert outcome(report) == APPLIED
    assert measurement() == ("SSE", {"SPD": Decimal("20.0"), "KWH": Decimal("1.5")})


def test_2_identical_report_with_equivalent_numbers_is_duplicate():
    first, second = submit(make_line("SPD=20.0"), make_line("SPD=20.00"))
    assert outcome(first) == APPLIED
    assert outcome(second) == DUPLICATE  # não fica em quarentena
    assert measurement() == ("SSE", {"SPD": Decimal("20.0")})  # não muda nada


def test_3_and_4_different_content_quarantines_all_including_applied():
    (first,) = submit(make_line("SPD=20"))
    assert outcome(first) == APPLIED

    (second,) = submit(make_line("SPD=25"))
    assert outcome(first) == CONFLICT  # o que já estava aplicado também
    assert outcome(second) == CONFLICT
    assert measurement() is None  # não sobra nenhuma revisão válida


def test_5_report_after_conflict_is_conflict_even_if_identical():
    submit(make_line("SPD=20"), make_line("SPD=25"))
    (third,) = submit(make_line("SPD=20"))
    assert outcome(third) == CONFLICT  # não é duplicado nem aplicado
    assert measurement() is None


def test_6_conflict_falls_back_to_other_revisions():
    rev0, rev1 = submit(
        make_line("SPD=10;KWH=1", rev=0, station="REB"),
        make_line("SPD=12", rev=1, station="ALF"),
    )
    assert measurement() == ("ALF", {"SPD": Decimal("12"), "KWH": Decimal("1")})

    (rev1_other,) = submit(make_line("SPD=13", rev=1, station="ALF"))
    assert outcome(rev0) == APPLIED
    assert outcome(rev1) == CONFLICT
    assert outcome(rev1_other) == CONFLICT
    # a revisão 1 deixa de contar: volta tudo à revisão 0, incluindo a estação
    assert measurement() == ("REB", {"SPD": Decimal("10"), "KWH": Decimal("1")})


@pytest.mark.parametrize("order", [("a", "b"), ("b", "a")])
def test_7_conflict_is_independent_of_arrival_order(order):
    base = make_line("SPD=5", rev=0)
    lines = {"a": make_line("SPD=20", rev=1), "b": make_line("SPD=25", rev=1)}
    ids = dict(zip(order, submit(base, *(lines[key] for key in order))[1:]))
    assert outcome(ids["a"]) == CONFLICT
    assert outcome(ids["b"]) == CONFLICT
    assert measurement() == ("SSE", {"SPD": Decimal("5")})


@pytest.mark.parametrize("order", [("a", "a_copy", "b"), ("b", "a", "a_copy")])
def test_7b_duplicates_also_become_conflict_in_any_order(order):
    lines = {"a": make_line("SPD=20"), "a_copy": make_line("SPD=20.00"), "b": make_line("SPD=25")}
    ids = dict(zip(order, submit(*(lines[key] for key in order))))
    assert {key: outcome(ids[key]) for key in lines} == {key: CONFLICT for key in lines}
    assert measurement() is None


def test_8_different_metric_keys_is_conflict():
    first, second = submit(make_line("SPD=20"), make_line("SPD=20;KWH=1"))
    assert outcome(first) == CONFLICT
    assert outcome(second) == CONFLICT


def test_9_different_station_is_conflict():
    first, second = submit(make_line("SPD=20", station="SSE"), make_line("SPD=20", station="MPO"))
    assert outcome(first) == CONFLICT
    assert outcome(second) == CONFLICT


def test_technical_error_rolls_back_and_keeps_report_pending(monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("falha simulada")

    monkeypatch.setattr(process_report_module, "_rebuild_measurement", boom)
    (report,) = submit(make_line("SPD=20"))
    assert outcome(report) == ("pending", None)
    assert revisions_count() == 0  # nada ficou meio escrito (A3)
    assert measurement() is None
