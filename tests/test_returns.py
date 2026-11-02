from datetime import date, timedelta

import pytest

from emporio.domain import returns
from emporio.domain.returns import QUESTIONS, evaluate

ORDER_DATE = date(2026, 2, 10)
RECEIVED_DATE = date(2026, 2, 14)


def test_invalid_reason_raises():
    with pytest.raises(ValueError):
        evaluate("outro", "delivered", ORDER_DATE, date(2026, 2, 16))


def test_cancelled_not_eligible():
    result = evaluate("arrependimento", "cancelled", ORDER_DATE, date(2026, 2, 16))
    assert result["resultado"] == returns.NOT_ELIGIBLE


@pytest.mark.parametrize("status", ["pending", "confirmed"])
def test_not_shipped_yet(status):
    result = evaluate("arrependimento", status, ORDER_DATE, date(2026, 2, 16))
    assert result["resultado"] == returns.NOT_ELIGIBLE
    assert "proximo_passo" in result


def test_shipped_without_received_needs_info():
    result = evaluate("arrependimento", "shipped", ORDER_DATE, date(2026, 2, 16))
    assert result["resultado"] == returns.NEEDS_INFO
    assert QUESTIONS["data_recebimento"] in result["falta_confirmar"]


def test_shipped_with_received_follows_delivered():
    result = evaluate(
        "arrependimento",
        "shipped",
        ORDER_DATE,
        date(2026, 2, 16),
        received_date=RECEIVED_DATE,
        online_purchase=True,
        special_item=False,
    )
    assert result["resultado"] == returns.ELIGIBLE


def test_regret_delivered_no_info_asks_all_three():
    result = evaluate("arrependimento", "delivered", ORDER_DATE, date(2026, 2, 16),
                      received_date=RECEIVED_DATE)
    assert result["resultado"] == returns.NEEDS_INFO
    # received_date já informada; faltam canal e item especial.
    assert QUESTIONS["compra_online"] in result["falta_confirmar"]
    assert QUESTIONS["item_especial"] in result["falta_confirmar"]


def test_regret_all_three_questions_when_nothing_known():
    result = evaluate("arrependimento", "delivered", ORDER_DATE, date(2026, 2, 16))
    assert result["resultado"] == returns.NEEDS_INFO
    assert set(result["falta_confirmar"]) == {
        QUESTIONS["compra_online"],
        QUESTIONS["item_especial"],
        QUESTIONS["data_recebimento"],
    }


def test_offline_purchase_not_eligible_even_with_missing():
    result = evaluate("arrependimento", "delivered", ORDER_DATE, date(2026, 2, 16),
                      online_purchase=False)
    assert result["resultado"] == returns.NOT_ELIGIBLE


def test_special_item_not_eligible():
    result = evaluate("arrependimento", "delivered", ORDER_DATE, date(2026, 2, 16),
                      special_item=True)
    assert result["resultado"] == returns.NOT_ELIGIBLE


def test_regret_within_deadline():
    result = evaluate("arrependimento", "delivered", ORDER_DATE, date(2026, 2, 21),
                      received_date=RECEIVED_DATE, online_purchase=True, special_item=False)
    assert result["resultado"] == returns.ELIGIBLE


def test_regret_past_deadline():
    result = evaluate("arrependimento", "delivered", ORDER_DATE, date(2026, 2, 22),
                      received_date=RECEIVED_DATE, online_purchase=True, special_item=False)
    assert result["resultado"] == returns.NOT_ELIGIBLE


def test_preference_does_not_ask_purchase_channel():
    result = evaluate("preferencia", "delivered", ORDER_DATE, date(2026, 2, 16))
    assert result["resultado"] == returns.NEEDS_INFO
    assert QUESTIONS["compra_online"] not in result["falta_confirmar"]


def test_received_date_out_of_range_needs_info():
    before = evaluate("arrependimento", "delivered", ORDER_DATE, date(2026, 2, 16),
                      received_date=date(2026, 2, 9))
    after = evaluate("arrependimento", "delivered", ORDER_DATE, date(2026, 2, 16),
                     received_date=date(2026, 2, 17))
    assert before["resultado"] == returns.NEEDS_INFO
    assert after["resultado"] == returns.NEEDS_INFO


def test_defect_within_30_days_in_store():
    result = evaluate("defeito", "delivered", ORDER_DATE, date(2026, 3, 5))
    assert result["resultado"] == returns.ELIGIBLE
    assert result["caminho"] == "troca_na_loja"


def test_defect_past_30_days_no_received_needs_info():
    today = ORDER_DATE + timedelta(days=45)
    result = evaluate("defeito", "delivered", ORDER_DATE, today)
    assert result["resultado"] == returns.NEEDS_INFO
    assert QUESTIONS["data_recebimento"] in result["falta_confirmar"]


def test_defect_legal_warranty():
    today = ORDER_DATE + timedelta(days=45)
    received = today - timedelta(days=40)
    result = evaluate("defeito", "delivered", ORDER_DATE, today, received_date=received)
    assert result["resultado"] == returns.ELIGIBLE
    assert result["caminho"] == "garantia_legal"


def test_defect_manufacturer_warranty():
    received = ORDER_DATE + timedelta(days=2)
    today = received + timedelta(days=100)
    result = evaluate("defeito", "delivered", ORDER_DATE, today, received_date=received)
    assert result["resultado"] == returns.NEEDS_INFO
    assert result["caminho"] == "garantia_fabricante"


def test_preference_uses_its_own_deadline(monkeypatch):
    monkeypatch.setattr(returns, "PREFERENCE_DAYS", 15)
    received = date(2026, 2, 14)
    today = received + timedelta(days=10)  # 10 dias desde o recebimento

    pref = evaluate("preferencia", "delivered", ORDER_DATE, today,
                    received_date=received, special_item=False)
    assert pref["resultado"] == returns.ELIGIBLE
    assert pref["prazo_dias"] == 15

    regret = evaluate("arrependimento", "delivered", ORDER_DATE, today,
                      received_date=received, online_purchase=True, special_item=False)
    assert regret["resultado"] == returns.NOT_ELIGIBLE


@pytest.mark.parametrize("reason", ["arrependimento", "preferencia"])
@pytest.mark.parametrize("online", [True, False, None])
@pytest.mark.parametrize("special", [True, False, None])
def test_no_received_date_never_eligible(reason, online, special):
    result = evaluate(reason, "delivered", ORDER_DATE, date(2026, 2, 21),
                      received_date=None, online_purchase=online, special_item=special)
    assert result["resultado"] != returns.ELIGIBLE
