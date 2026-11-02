"""Regras puras de pagamento, calculadas sempre em centavos inteiros.

Interpretação adotada (a seção 3.1 do manual prevalece sobre a tabela):
- 1x no crédito é sempre permitido, sem valor mínimo de parcela;
- 2x–3x: parcela mínima de R$ 50,00;
- 4x–6x: parcela mínima de R$ 80,00;
- 7x–12x: parcela mínima de R$ 100,00; até 12x sem juros;
- o desconto de 5% do PIX incide só sobre a parte em preço de tabela
  (não acumula com preço promocional);
- combinação de formas de pagamento é liberada acima de R$ 2.000,00.

Dinheiro nunca é manipulado em float: entra via to_cents (half-up) e só volta
a float em from_cents para exibição.
"""

from decimal import ROUND_HALF_UP, Decimal

from emporio.utils import brl

PIX_DISCOUNT_PCT = 5
COMBINED_PAYMENT_MIN_CENTS = 200_000


def to_cents(value: float) -> int:
    # Decimal(str(value)) evita o ruído binário do float; ROUND_HALF_UP garante
    # o arredondamento comercial (0,125 -> 0,13), diferente do round() nativo.
    cents = Decimal(str(value)) * 100
    return int(cents.quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def from_cents(cents: int) -> float:
    return cents / 100


def min_installment_cents(n: int) -> int:
    if n == 1:
        return 0
    if 2 <= n <= 3:
        return 5_000
    if 4 <= n <= 6:
        return 8_000
    if 7 <= n <= 12:
        return 10_000
    raise ValueError(f"Número de parcelas fora de 1..12: {n}")


def max_installments(total_cents: int) -> int:
    best = 1
    for n in range(1, 13):
        if total_cents // n >= min_installment_cents(n):
            best = n
    return best


def split_installments(total_cents: int, n: int) -> list[int]:
    base = total_cents // n
    installments = [base] * n
    installments[-1] += total_cents - base * n
    return installments


def pix_total_cents(total_cents: int, pix_eligible_cents: int) -> int:
    discount = Decimal(pix_eligible_cents) * PIX_DISCOUNT_PCT / 100
    discount_cents = int(discount.quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    return total_cents - discount_cents


def _credit_block(total_cents: int) -> dict:
    n = max_installments(total_cents)
    installments = split_installments(total_cents, n)
    block = {
        "max_parcelas_sem_juros": n,
        "valor_parcela": brl(from_cents(installments[0])),
    }
    if installments[-1] != installments[0]:
        block["ultima_parcela"] = brl(from_cents(installments[-1]))
    return block


def payment_options(total_cents: int, pix_eligible_cents: int | None) -> dict:
    if total_cents <= 0:
        raise ValueError("Valor total deve ser positivo.")

    if pix_eligible_cents is None:
        pix = {
            "total": None,
            "calculado": False,
            "observacao": (
                "Desconto do PIX não calculado: depende de quais produtos "
                "compõem o valor."
            ),
        }
    elif pix_eligible_cents == 0:
        pix = {
            "total": brl(from_cents(total_cents)),
            "calculado": True,
            "desconto_aplicado": False,
            "observacao": "O desconto do PIX não acumula com preço promocional.",
        }
    else:
        pix = {
            "total": brl(from_cents(pix_total_cents(total_cents, pix_eligible_cents))),
            "calculado": True,
            "desconto_aplicado": True,
        }

    return {
        "valor_base": brl(from_cents(total_cents)),
        "pix": pix,
        "debito": {"total": brl(from_cents(total_cents))},
        "boleto": {
            "total": brl(from_cents(total_cents)),
            "observacao": "Compensação em até 3 dias úteis.",
        },
        "credito": _credit_block(total_cents),
        "pode_combinar_formas": total_cents > COMBINED_PAYMENT_MIN_CENTS,
    }


def check_installments(total_cents: int, n: int) -> dict:
    if not 1 <= n <= 12:
        return {
            "permitido": False,
            "motivo": f"Parcelamento aceito apenas de 1x a 12x (pedido: {n}x).",
        }

    installments = split_installments(total_cents, n)
    minimum = min_installment_cents(n)
    if installments[0] < minimum:
        return {
            "permitido": False,
            "motivo": (
                f"Parcela de {brl(from_cents(installments[0]))} fica abaixo do "
                f"mínimo de {brl(from_cents(minimum))} para {n}x."
            ),
            "max_parcelas_sem_juros": max_installments(total_cents),
        }

    result = {
        "permitido": True,
        "valor_parcela": brl(from_cents(installments[0])),
    }
    if installments[-1] != installments[0]:
        result["ultima_parcela"] = brl(from_cents(installments[-1]))
    return result
