from emporio.utils import brl, normalize, normalize_phone, only_digits


def test_normalize_accents_case_and_spaces():
    assert normalize("Violão Clássico") == "violao classico"
    assert normalize("  MÚSICA   ao   VIVO ") == "musica ao vivo"
    assert normalize("GUITARRA") == "guitarra"


def test_normalize_empty_and_none():
    assert normalize(None) == ""
    assert normalize("") == ""
    assert normalize("   ") == ""


def test_only_digits():
    assert only_digits("(67) 99654-7821") == "67996547821"
    assert only_digits("abc123def456") == "123456"
    assert only_digits(None) == ""
    assert only_digits("") == ""


def test_normalize_phone_examples():
    assert normalize_phone("+55 (67) 99654-7821") == "67996547821"
    assert normalize_phone("(67) 99654-7821") == "67996547821"
    assert normalize_phone("99654-7821") == "996547821"


def test_normalize_phone_none():
    assert normalize_phone(None) == ""
    assert normalize_phone("") == ""


def test_brl_formatting():
    assert brl(0) == "R$ 0,00"
    assert brl(429.9) == "R$ 429,90"
    assert brl(1234.5) == "R$ 1.234,50"
    assert brl(1000000) == "R$ 1.000.000,00"
