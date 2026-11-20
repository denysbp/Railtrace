from decimal import Decimal

from app.domain import (
    Revision,
    RevisionContent,
    RevisionOutcome,
    apply_revisions,
    classify_revision,
    parse_report,
    same_content,
)


def content(station="SSE", **metrics):
    return RevisionContent(
        station=station,
        metrics={k: (None if v is None else Decimal(v)) for k, v in metrics.items()},
    )


# --- parse_report ----------------------------------------------------------

def test_parse_report_reads_fields_removals_and_no_station():
    parsed = parse_report("$TRN,TS-0001,2026-11-02T08:00:00Z,1,-,SPD=20.00;AX8=-*00")
    assert parsed.serial == "TS-0001"
    assert parsed.measured_at == "2026-11-02T08:00:00Z"
    assert parsed.rev == 1
    assert parsed.station is None
    assert parsed.metrics == {"SPD": Decimal("20.00"), "AX8": None}


# --- same_content (R2) -----------------------------------------------------

def test_values_are_compared_as_numbers():
    assert same_content(content(SPD="20.0"), content(SPD="20.00"))
    assert same_content(content(AX1="11.6"), content(AX1="11.60"))


def test_different_value_is_different_content():
    assert not same_content(content(SPD="20"), content(SPD="25"))


def test_different_metric_keys_are_different_content():
    assert not same_content(content(SPD="20"), content(SPD="20", KWH="1"))


def test_removal_differs_from_value():
    assert not same_content(content(AX8=None), content(AX8="0"))


def test_different_station_is_different_content():
    assert not same_content(content("SSE", SPD="20"), content("MPO", SPD="20"))
    assert not same_content(content(None, SPD="20"), content("SSE", SPD="20"))


# --- classify_revision (R2 + R4) --------------------------------------------

def test_first_revision_is_new():
    assert classify_revision(content(SPD="20"), [], False) is RevisionOutcome.NEW


def test_identical_revision_is_duplicate():
    assert classify_revision(content(SPD="20.00"), [content(SPD="20.0")], False) is RevisionOutcome.DUPLICATE


def test_same_identity_different_content_is_conflict():
    assert classify_revision(content(SPD="25"), [content(SPD="20")], False) is RevisionOutcome.CONFLICT


def test_identity_already_in_conflict_is_always_conflict():
    # igual a uma das versões, mas a identidade já está em conflito: não é duplicado
    existing = [content(SPD="20"), content(SPD="25")]
    assert classify_revision(content(SPD="20"), existing, True) is RevisionOutcome.CONFLICT


# --- apply_revisions (R3) ---------------------------------------------------

def test_revisions_apply_in_rev_order_regardless_of_arrival():
    r0 = Revision(0, content("REB", SPD="10", KWH="1", AX8="30"))
    r1 = Revision(1, content("ALF", SPD="12", AX8=None))
    expected = content("ALF", SPD="12", KWH="1")  # KWH mantém-se, AX8 removida, estação do rev mais alto
    assert apply_revisions([r0, r1]) == expected
    assert apply_revisions([r1, r0]) == expected


def test_no_revisions_or_all_removed_gives_no_metrics():
    assert apply_revisions([]).metrics == {}
    assert apply_revisions([Revision(0, content(SPD="1")), Revision(1, content(SPD=None))]).metrics == {}
