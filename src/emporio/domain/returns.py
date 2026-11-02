"""Elegibilidade de troca e devolução com três estados.

Princípio central: informação desconhecida NUNCA vira aprovação. Toda avaliação
termina em um de três estados: "elegivel" (tudo confirmado e dentro do prazo),
"nao_elegivel" (algum dado confirmado impede) ou "precisa_confirmacao" (falta
algo que só o cliente ou a equipe pode informar).

O CSV não traz data de recebimento, canal da compra nem indicação de item
personalizado/"venda final" — esses dados vêm do cliente. A previsão de entrega
(estimated_delivery) NUNCA é tratada como data de recebimento.

Interpretações do manual:
- Arrependimento (4.1): só compra online; 7 dias corridos após o RECEBIMENTO.
- Preferência (4.3): 7 dias após o recebimento, sujeito à disponibilidade.
- Itens da 4.4 (personalizados/ajuste sob encomenda e "venda final") não entram
  em arrependimento nem preferência, mas seguem cobertos contra defeito de
  fabricação — a 4.4 restringe apenas arrependimento/preferência.
- Defeito (4.2 e 8): troca direta até 30 dias após a COMPRA; depois, garantia
  legal de 90 dias contados do RECEBIMENTO (8.1), podendo a loja intermediar;
  depois disso, só garantia do fabricante (8.2), que não está no sistema e nunca
  é confirmada pelo agente.
"""

from datetime import date

REGRET_DAYS = 7
PREFERENCE_DAYS = 7
DEFECT_DAYS = 30
LEGAL_WARRANTY_DAYS = 90

REASONS = ("arrependimento", "defeito", "preferencia")

ELIGIBLE = "elegivel"
NOT_ELIGIBLE = "nao_elegivel"
NEEDS_INFO = "precisa_confirmacao"

QUESTIONS = {
    "data_recebimento": "Em que data você recebeu o produto?",
    "compra_online": "A compra foi feita online (site ou WhatsApp) ou na loja física?",
    "item_especial": (
        "O produto teve personalização ou ajuste sob encomenda, ou foi comprado "
        "em liquidação com aviso de 'venda final'?"
    ),
}

_DEFECT_EXCLUSIONS = (
    "Não cobre danos por mau uso, quedas, exposição a umidade excessiva "
    "ou modificações não autorizadas."
)
_REGRET_CONDITIONS = [
    "Produto na embalagem original, sem sinais de uso, com todos os acessórios e manuais.",
    "Reembolso na mesma forma de pagamento original em até 10 dias úteis.",
    "Frete de devolução por conta da loja.",
]
_PREFERENCE_CONDITIONS = [
    "Produto em perfeito estado e na embalagem original.",
    "Sujeito à disponibilidade do produto desejado.",
    "Diferenças de valor serão cobradas ou reembolsadas conforme o caso.",
]


def _defect(order_date: date, today: date, received_date: date | None) -> dict:
    days_since_purchase = (today - order_date).days

    if days_since_purchase <= DEFECT_DAYS:
        return {
            "resultado": ELIGIBLE,
            "caminho": "troca_na_loja",
            "motivo": "Dentro dos 30 dias da compra, a troca por defeito é feita direto na loja.",
            "dias_desde_compra": days_since_purchase,
            "prazo_dias": DEFECT_DAYS,
            "condicoes": [_DEFECT_EXCLUSIONS],
        }

    if received_date is None:
        return {
            "resultado": NEEDS_INFO,
            "motivo": (
                "Passou dos 30 dias da compra para troca direta. A garantia legal "
                "de 90 dias conta a partir do recebimento, então preciso dessa data."
            ),
            "dias_desde_compra": days_since_purchase,
            "falta_confirmar": [QUESTIONS["data_recebimento"]],
        }

    days_since_received = (today - received_date).days
    if days_since_received <= LEGAL_WARRANTY_DAYS:
        return {
            "resultado": ELIGIBLE,
            "caminho": "garantia_legal",
            "motivo": "Dentro da garantia legal de 90 dias contados do recebimento.",
            "dias_desde_compra": days_since_purchase,
            "dias_desde_recebimento": days_since_received,
            "prazo_dias": LEGAL_WARRANTY_DAYS,
            "condicoes": [
                "O cliente aciona a garantia junto ao fabricante.",
                "A Empório da Música pode intermediar o processo mediante solicitação.",
            ],
        }

    return {
        "resultado": NEEDS_INFO,
        "caminho": "garantia_fabricante",
        "motivo": (
            "Passou da garantia legal de 90 dias. Pode haver garantia do fabricante "
            "(de 6 meses a 2 anos, conforme o certificado), mas isso não está no sistema."
        ),
        "dias_desde_compra": days_since_purchase,
        "dias_desde_recebimento": days_since_received,
        "proximo_passo": (
            "Verificar o certificado de garantia que acompanha o produto e encaminhar "
            "para a equipe intermediar com o fabricante."
        ),
    }


def _regret_or_preference(
    reason: str,
    today: date,
    received_date: date | None,
    online_purchase: bool | None,
    special_item: bool | None,
) -> dict:
    # Negativos definitivos primeiro: dados confirmados que já impedem.
    if reason == "arrependimento" and online_purchase is False:
        return {
            "resultado": NOT_ELIGIBLE,
            "motivo": (
                "O direito de arrependimento vale só para compra online. Em compra "
                "na loja física cabe troca por preferência ou por defeito."
            ),
        }
    if special_item is True:
        return {
            "resultado": NOT_ELIGIBLE,
            "motivo": (
                "Itens personalizados/sob encomenda ou de liquidação com 'venda final' "
                "não entram em troca por arrependimento ou preferência (seção 4.4)."
            ),
        }

    missing: list[str] = []
    if reason == "arrependimento" and online_purchase is None:
        missing.append(QUESTIONS["compra_online"])
    if special_item is None:
        missing.append(QUESTIONS["item_especial"])
    if received_date is None:
        missing.append(QUESTIONS["data_recebimento"])

    if missing:
        return {"resultado": NEEDS_INFO, "falta_confirmar": missing}

    days_since_received = (today - received_date).days
    condicoes = _REGRET_CONDITIONS if reason == "arrependimento" else _PREFERENCE_CONDITIONS

    if days_since_received <= REGRET_DAYS:
        return {
            "resultado": ELIGIBLE,
            "prazo_dias": REGRET_DAYS,
            "dias_desde_recebimento": days_since_received,
            "condicoes": list(condicoes),
        }

    return {
        "resultado": NOT_ELIGIBLE,
        "motivo": (
            f"Fora do prazo de {REGRET_DAYS} dias após o recebimento "
            f"({days_since_received} dias já se passaram)."
        ),
        "prazo_dias": REGRET_DAYS,
        "dias_desde_recebimento": days_since_received,
    }


def evaluate(
    reason: str,
    status: str,
    order_date: date,
    today: date,
    received_date: date | None = None,
    online_purchase: bool | None = None,
    special_item: bool | None = None,
) -> dict:
    if reason not in REASONS:
        raise ValueError(f"Motivo inválido: {reason}")

    if status == "cancelled":
        return {
            "resultado": NOT_ELIGIBLE,
            "motivo": "Pedido cancelado, não há produto a devolver.",
        }

    if status in ("pending", "confirmed"):
        return {
            "resultado": NOT_ELIGIBLE,
            "motivo": "O pedido ainda não foi enviado, então não é caso de devolução.",
            "proximo_passo": (
                "Se o cliente desistiu, encaminhar o pedido de cancelamento para a equipe."
            ),
        }

    if received_date is not None and not (order_date <= received_date <= today):
        return {
            "resultado": NEEDS_INFO,
            "motivo": "A data de recebimento informada não é válida para este pedido.",
            "falta_confirmar": [QUESTIONS["data_recebimento"]],
        }

    shipped_note: str | None = None
    if status == "shipped":
        if received_date is None:
            return {
                "resultado": NEEDS_INFO,
                "motivo": (
                    "O pedido ainda consta como enviado; os prazos contam a partir "
                    "do recebimento."
                ),
                "falta_confirmar": [QUESTIONS["data_recebimento"]],
            }
        shipped_note = (
            "O sistema ainda mostra o pedido como 'enviado', mas seguimos pela data "
            "de recebimento informada."
        )

    if reason == "defeito":
        result = _defect(order_date, today, received_date)
    else:
        result = _regret_or_preference(
            reason, today, received_date, online_purchase, special_item
        )

    if shipped_note is not None:
        existing = result.get("motivo")
        result["motivo"] = f"{existing} {shipped_note}".strip() if existing else shipped_note

    return result
