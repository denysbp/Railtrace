"""R2 (duplicates), R3 (revisions), and R4 (conflicts) in process_report, against the test DB."""

import importlib
from decimal import Decimal

import pytest

# The module (not the process_report function that services/__init__.py re-exports under the same name)
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
    assert outcome(second) == DUPLICATE  # does not go into quarantine
    assert measurement() == ("SSE", {"SPD": Decimal("20.0")})  # changes nothing


def test_3_and_4_different_content_quarantines_all_including_applied():
    (first,) = submit(make_line("SPD=20"))
    assert outcome(first) == APPLIED

    (second,) = submit(make_line("SPD=25"))
    assert outcome(first) == CONFLICT  # the already applied one too
    assert outcome(second) == CONFLICT
    assert measurement() is None  # no valid revision remains


def test_5_report_after_conflict_is_conflict_even_if_identical():
    submit(make_line("SPD=20"), make_line("SPD=25"))
    (third,) = submit(make_line("SPD=20"))
    assert outcome(third) == CONFLICT  # neither duplicate nor applied
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
    # revision 1 no longer counts: everything falls back to revision 0, including the station
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
        raise RuntimeError("simulated failure")

    monkeypatch.setattr(process_report_module, "_rebuild_measurement", boom)
    (report,) = submit(make_line("SPD=20"))
    assert outcome(report) == ("pending", None)
    assert revisions_count() == 0  # nothing was half-written (A3)
    assert measurement() is None
