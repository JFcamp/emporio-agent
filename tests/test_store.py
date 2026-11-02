from datetime import UTC, datetime

from emporio.config import STORE_TZ
from emporio.domain.store import opening_status

# 02/03/2026 é uma segunda-feira; a semana usada nos casos vai de 02 a 08/03.


def _dt(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 3, day, hour, minute, tzinfo=STORE_TZ)


def test_monday_open():
    status = opening_status(_dt(2, 10))
    assert status == {"aberta": True, "fecha_as": "18:00"}


def test_monday_closing_time_is_closed():
    status = opening_status(_dt(2, 18))
    assert status == {"aberta": False, "reabre": "amanhã às 09:00"}


def test_monday_before_opening():
    status = opening_status(_dt(2, 8))
    assert status == {"aberta": False, "reabre": "hoje às 09:00"}


def test_saturday_open_before_one():
    status = opening_status(_dt(7, 12, 59))
    assert status == {"aberta": True, "fecha_as": "13:00"}


def test_saturday_closing_time_reopens_monday():
    status = opening_status(_dt(7, 13))
    assert status == {"aberta": False, "reabre": "segunda às 09:00"}


def test_sunday_closed_reopens_tomorrow():
    status = opening_status(_dt(8, 10))
    assert status == {"aberta": False, "reabre": "amanhã às 09:00"}


def test_utc_is_converted_to_store_tz():
    # 13:00 UTC = 09:00 em Campo Grande (UTC-4) numa segunda -> aberta.
    utc_dt = datetime(2026, 3, 2, 13, 0, tzinfo=UTC)
    status = opening_status(utc_dt)
    assert status == {"aberta": True, "fecha_as": "18:00"}
