from app.domain import check_sum_valid, is_malformated_fields, is_malformated_form


def line(body):
    """Report with a correct checksum for the given body (without "$" or "*")."""
    checksum = 0
    for byte in body.encode():
        checksum ^= byte
    return f"${body}*{checksum:02X}"


VALID = line("TRN,TS-0001,2026-11-02T08:00:00Z,0,-,SPD=20.0;KWH=1.5")


# --- check 1: form $...*hh --------------------------------------------------

def test_valid_report_has_valid_form_and_fields():
    assert not is_malformated_form(VALID)
    assert not is_malformated_fields(VALID)
    assert check_sum_valid(VALID)


def test_form_requires_single_dollar_and_star_and_two_hex_digits():
    assert is_malformated_form(VALID[1:])                 # without "$"
    assert is_malformated_form("$" + VALID)               # another "$"
    assert is_malformated_form(VALID.replace("TS-", "TS$"))
    assert is_malformated_form(VALID + "*1")              # another "*"
    assert is_malformated_form(VALID.split("*")[0])       # without "*hh"
    assert is_malformated_form(VALID[:-1])                # 1 digit
    assert is_malformated_form(VALID + "0")               # 3 digits
    assert is_malformated_form(VALID[:-2] + "zz")         # not hexadecimal


def test_form_does_not_look_at_fields():
    # correct form, wrong fields: the form passes (fields are check 3)
    five_fields = line("TRN,TS-0001,2026-11-02T08:00:00Z,0,-")
    assert not is_malformated_form(five_fields)
    assert is_malformated_fields(five_fields)


# --- check 3: fields ---------------------------------------------------------

def test_fields_rules():
    assert is_malformated_fields(line("GPS,TS-0001,2026-11-02T08:00:00Z,0,-,SPD=1"))  # type
    assert is_malformated_fields(line("TRN,,2026-11-02T08:00:00Z,0,-,SPD=1"))         # empty serial
    assert is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,a,-,SPD=1"))  # rev
    assert is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,0,,SPD=1"))   # empty station
    assert is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,0,-,SPD=1x")) # value
    assert is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,0,-,SPD=1;SPD=2"))  # repeated
    assert is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,0,-,"))       # 0 metrics
    assert is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,0,-,SPD=1;"))  # empty pair


def test_fields_accept_removal_and_unknown_metric_names():
    # "-" is removal (R3); unknown names are unknown_metric, not malformed
    assert not is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,1,-,AX8=-;DOOR=1"))


def test_fields_do_not_check_the_clock():
    # invalid date is clock_invalid (check 7), not malformed
    assert not is_malformated_fields(line("TRN,TS-0001,ontem,0,-,SPD=1"))
