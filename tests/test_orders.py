from datetime import date

import pytest

from emporio.config import get_settings
from emporio.tools import orders
from emporio.tools.orders import NOT_VERIFIED, evaluate_return, get_order_status


@pytest.fixture
def reference_date_feb20():
    settings = get_settings()
    original = settings.reference_date
    settings.reference_date = date(2026, 2, 20)
    yield
    settings.reference_date = original


def test_verify_with_phone_full():
    assert get_order_status(8, "(67) 99654-7821")["verificado"] is True
    assert get_order_status(8, "+55 67 99654-7821")["verificado"] is True


def test_verify_phone_without_ddd_fails():
    assert get_order_status(8, "99654-7821") == NOT_VERIFIED
    assert get_order_status(8, "(11) 99654-7821") == NOT_VERIFIED


def test_verify_email_case_and_spaces():
    assert get_order_status(8, "  ANACAROL.FERREIRA@COLDMAIL.COM ")["verificado"] is True


def test_verify_wrong_email_fails():
    assert get_order_status(8, "outro@coldmail.com") == NOT_VERIFIED


def test_nonexistent_order_same_as_not_verified():
    # Contato válido de um cliente, mas pedido 999 não existe.
    result = get_order_status(999, "anacarol.ferreira@coldmail.com")
    assert result == NOT_VERIFIED


def test_order_8_status_shipped_with_tracking():
    result = get_order_status(8, "anacarol.ferreira@coldmail.com")
    assert result["status"] == "Enviado"
    assert result.get("codigo_rastreio")


def test_no_order_leaks_pii_or_delivered_key():
    with get_settings_connection() as conn:
        rows = conn.execute(
            """
            SELECT o.order_id, c.email, c.name, c.phone_digits
            FROM orders o JOIN customers c ON c.customer_id = o.customer_id
            """
        ).fetchall()
    for order_id, email, name, phone_digits in rows:
        result = get_order_status(order_id, email)
        assert result["verificado"] is True
        assert "entregue_em" not in result
        text = str(result)
        assert email not in text
        assert phone_digits not in text
        assert name not in text  # nome completo não aparece


def test_evaluate_return_needs_info_has_estimate_warning(reference_date_feb20):
    result = evaluate_return(7, "leticia.rocha@jmail.com", "arrependimento")
    assert result["resultado"] == "precisa_confirmacao"
    assert "previsao_de_entrega_registrada" in result
    assert "atencao" in result


def test_evaluate_return_eligible(reference_date_feb20):
    result = evaluate_return(
        7, "leticia.rocha@jmail.com", "arrependimento",
        received_date="2026-02-18", online_purchase=True, special_item=False,
    )
    assert result["resultado"] == "elegivel"


def test_evaluate_return_bad_date_format(reference_date_feb20):
    result = evaluate_return(7, "leticia.rocha@jmail.com", "arrependimento",
                             received_date="18/02/2026")
    assert result["verificado"] is True
    assert "erro" in result


def test_evaluate_return_wrong_contact():
    result = evaluate_return(7, "errado@jmail.com", "arrependimento")
    assert result == NOT_VERIFIED


def get_settings_connection():
    from emporio.data.db import connect

    return connect()


def test_payment_label_variants():
    assert orders.payment_label("credit_6x") == "Cartão de crédito em 6x"
    assert orders.payment_label("pix") == "PIX"
    assert orders.payment_label("debit") == "Cartão de débito"
    assert orders.payment_label("boleto") == "Boleto bancário"
