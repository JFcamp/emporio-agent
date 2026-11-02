import pytest

from emporio.domain.payments import (
    check_installments,
    max_installments,
    min_installment_cents,
    payment_options,
    pix_total_cents,
    split_installments,
    to_cents,
)


def test_to_cents_half_up():
    assert to_cents(0.125) == 13
    assert to_cents(439.2) == 43920


@pytest.mark.parametrize(
    "total_cents, expected",
    [
        (4_000, 1),
        (15_000, 3),
        (50_000, 6),
        (59_990, 6),
        (90_000, 9),
        (219_900, 12),
    ],
)
def test_max_installments(total_cents, expected):
    assert max_installments(total_cents) == expected


def test_split_installments_specific():
    assert split_installments(10_000, 3) == [3333, 3333, 3334]


@pytest.mark.parametrize(
    "total_cents, n",
    [
        (10_000, 3),
        (99_999, 7),
        (219_900, 12),
        (43_921, 6),
        (1, 1),
    ],
)
def test_split_installments_sum_closes_total(total_cents, n):
    assert sum(split_installments(total_cents, n)) == total_cents


def test_pix_full_eligible():
    options = payment_options(100_000, 100_000)
    assert options["pix"]["total"] == "R$ 950,00"
    assert options["pix"]["desconto_aplicado"] is True


def test_pix_zero_eligible():
    options = payment_options(100_000, 0)
    assert options["pix"]["total"] == "R$ 1.000,00"
    assert options["pix"]["desconto_aplicado"] is False


def test_pix_none_eligible():
    options = payment_options(100_000, None)
    assert options["pix"]["total"] is None
    assert options["pix"]["calculado"] is False


def test_pix_total_mixed_order():
    assert pix_total_cents(150_000, 100_000) == 145_000


def test_check_installments_below_minimum():
    result = check_installments(59_990, 10)
    assert result["permitido"] is False
    assert result["max_parcelas_sem_juros"] == 6


def test_check_installments_ok():
    result = check_installments(219_900, 12)
    assert result["permitido"] is True
    assert result["valor_parcela"] == "R$ 183,25"


@pytest.mark.parametrize(
    "total_cents, expected",
    [
        (200_000, False),
        (200_001, True),
    ],
)
def test_combined_payment_threshold(total_cents, expected):
    options = payment_options(total_cents, None)
    assert options["pode_combinar_formas"] is expected


@pytest.mark.parametrize("n", [13, 0])
def test_min_installment_cents_invalid(n):
    with pytest.raises(ValueError):
        min_installment_cents(n)
