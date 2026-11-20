from app.domain import check_sum_valid, is_malformated_fields, is_malformated_form


def line(body):
    """Relatório com checksum correto para o corpo dado (sem "$" nem "*")."""
    checksum = 0
    for byte in body.encode():
        checksum ^= byte
    return f"${body}*{checksum:02X}"


VALID = line("TRN,TS-0001,2026-11-02T08:00:00Z,0,-,SPD=20.0;KWH=1.5")


# --- verificação 1: forma $...*hh -------------------------------------------

def test_valid_report_has_valid_form_and_fields():
    assert not is_malformated_form(VALID)
    assert not is_malformated_fields(VALID)
    assert check_sum_valid(VALID)


def test_form_requires_single_dollar_and_star_and_two_hex_digits():
    assert is_malformated_form(VALID[1:])                 # sem "$"
    assert is_malformated_form("$" + VALID)               # outro "$"
    assert is_malformated_form(VALID.replace("TS-", "TS$"))
    assert is_malformated_form(VALID + "*1")              # outro "*"
    assert is_malformated_form(VALID.split("*")[0])       # sem "*hh"
    assert is_malformated_form(VALID[:-1])                # 1 dígito
    assert is_malformated_form(VALID + "0")               # 3 dígitos
    assert is_malformated_form(VALID[:-2] + "zz")         # não hexadecimal


def test_form_does_not_look_at_fields():
    # forma certa, campos errados: a forma passa (os campos são a verificação 3)
    five_fields = line("TRN,TS-0001,2026-11-02T08:00:00Z,0,-")
    assert not is_malformated_form(five_fields)
    assert is_malformated_fields(five_fields)


# --- verificação 3: campos ---------------------------------------------------

def test_fields_rules():
    assert is_malformated_fields(line("GPS,TS-0001,2026-11-02T08:00:00Z,0,-,SPD=1"))  # tipo
    assert is_malformated_fields(line("TRN,,2026-11-02T08:00:00Z,0,-,SPD=1"))         # serial vazio
    assert is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,a,-,SPD=1"))  # rev
    assert is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,0,,SPD=1"))   # estação vazia
    assert is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,0,-,SPD=1x")) # valor
    assert is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,0,-,SPD=1;SPD=2"))  # repetida
    assert is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,0,-,"))       # 0 métricas
    assert is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,0,-,SPD=1;"))  # par vazio


def test_fields_accept_removal_and_unknown_metric_names():
    # "-" é remoção (R3); nomes desconhecidos são unknown_metric, não malformed
    assert not is_malformated_fields(line("TRN,TS-0001,2026-11-02T08:00:00Z,1,-,AX8=-;DOOR=1"))


def test_fields_do_not_check_the_clock():
    # data inválida é clock_invalid (verificação 7), não malformed
    assert not is_malformated_fields(line("TRN,TS-0001,ontem,0,-,SPD=1"))
