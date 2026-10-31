import re
import unicodedata

_WHITESPACE = re.compile(r"\s+")
_NON_DIGITS = re.compile(r"\D")


def normalize(text: str | None) -> str:
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    collapsed = _WHITESPACE.sub(" ", without_accents)
    return collapsed.strip().lower()


def only_digits(text: str | None) -> str:
    if not text:
        return ""
    return _NON_DIGITS.sub("", text)


def normalize_phone(text: str | None) -> str:
    digits = only_digits(text)
    # Remove apenas o código do país (55); DDD e número ficam intactos.
    if len(digits) in (12, 13) and digits.startswith("55"):
        return digits[2:]
    return digits


def brl(value: float) -> str:
    cents = round(value * 100)
    sign = "-" if cents < 0 else ""
    cents = abs(cents)
    integer_part, decimal_part = divmod(cents, 100)
    integer_str = f"{integer_part:,}".replace(",", ".")
    return f"{sign}R$ {integer_str},{decimal_part:02d}"
