"""Consultas de pedido com verificação simplificada de identidade.

O pedido só é revelado quando o número confere com um contato (e-mail ou
telefone completo) do dono do pedido. Pedido inexistente e contato que não
confere devolvem a MESMA resposta (NOT_VERIFIED), para não vazar se o pedido
existe. A previsão de entrega (estimated_delivery) nunca é tratada como data de
recebimento.
"""

import re
import sqlite3
from datetime import date

from emporio.config import get_settings
from emporio.data.db import connect
from emporio.domain import returns
from emporio.utils import brl, normalize, normalize_phone

STATUS = {
    "pending": (
        "Aguardando confirmação do pagamento",
        "Assim que o pagamento for confirmado, o pedido segue para separação.",
    ),
    "confirmed": (
        "Pagamento confirmado, em separação",
        "O código de rastreio é enviado por e-mail e WhatsApp quando o pedido for despachado.",
    ),
    "shipped": (
        "Enviado",
        "Dá para acompanhar pelo código de rastreio no site dos Correios ou da Jadlog.",
    ),
    "delivered": ("Entregue", None),
    "cancelled": ("Cancelado", None),
}

NOT_VERIFIED = {
    "verificado": False,
    "mensagem": (
        "Não consegui confirmar esse pedido com os dados informados. Peça ao "
        "cliente para conferir o número do pedido e o e-mail ou telefone usado "
        "na compra."
    ),
}

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def payment_label(code: str | None) -> str | None:
    if code is None:
        return None
    if code == "pix":
        return "PIX"
    if code == "debit":
        return "Cartão de débito"
    if code == "boleto":
        return "Boleto bancário"
    credit = re.match(r"^credit_(\d{1,2})x$", code)
    if credit:
        return f"Cartão de crédito em {credit.group(1)}x"
    return code


def _verify(conn: sqlite3.Connection, order_id: int, contact: str) -> sqlite3.Row | None:
    # Identificação simplificada (não é autenticação forte): confere o contato
    # informado contra os dados do cliente dono do pedido.
    row = conn.execute(
        """
        SELECT o.*, c.name AS customer_name, c.email AS customer_email,
               c.phone_digits AS customer_phone_digits
        FROM orders o
        JOIN customers c ON c.customer_id = o.customer_id
        WHERE o.order_id = ?
        """,
        (order_id,),
    ).fetchone()
    if row is None:
        return None

    if "@" in contact:
        if normalize(contact) == normalize(row["customer_email"] or ""):
            return row
        return None

    provided = normalize_phone(contact)
    if provided and provided == (row["customer_phone_digits"] or ""):
        return row
    return None


def _items(conn: sqlite3.Connection, order_id: int) -> list[str]:
    rows = conn.execute(
        """
        SELECT oi.quantity, p.name
        FROM order_items oi
        JOIN products p ON p.product_id = oi.product_id
        WHERE oi.order_id = ?
        ORDER BY oi.rowid
        """,
        (order_id,),
    ).fetchall()
    return [f"{row['quantity']}x {row['name']}" for row in rows]


def get_order_status(order_id: int, contact: str) -> dict:
    with connect() as conn:
        row = _verify(conn, order_id, contact)
        if row is None:
            return dict(NOT_VERIFIED)

        label, next_step = STATUS.get(row["status"], (row["status"], None))
        first_name = (row["customer_name"] or "").split()[0] if row["customer_name"] else ""

        result: dict = {
            "verificado": True,
            "pedido": row["order_id"],
            "cliente_primeiro_nome": first_name,
            "data_pedido": row["order_date"],
            "status": label,
            "itens": _items(conn, row["order_id"]),
            "total": brl(row["total_brl"]),
            "pagamento": payment_label(row["payment_method"]),
        }
        if row["tracking_code"]:
            result["codigo_rastreio"] = row["tracking_code"]
        if row["estimated_delivery"]:
            result["previsao_de_entrega"] = row["estimated_delivery"]
        if row["notes"]:
            result["observacao"] = row["notes"]
        if next_step:
            result["proximo_passo"] = next_step
        return result


def evaluate_return(
    order_id: int,
    contact: str,
    reason: str,
    received_date: str | None = None,
    online_purchase: bool | None = None,
    special_item: bool | None = None,
) -> dict:
    with connect() as conn:
        row = _verify(conn, order_id, contact)
        if row is None:
            return dict(NOT_VERIFIED)

        parsed_received: date | None = None
        if received_date is not None:
            if not _DATE_RE.match(received_date):
                return {
                    "verificado": True,
                    "erro": "data_recebimento deve estar no formato AAAA-MM-DD.",
                }
            parsed_received = date.fromisoformat(received_date)

        settings = get_settings()
        today = settings.today()
        order_date = date.fromisoformat(row["order_date"])

        evaluation = returns.evaluate(
            reason=reason,
            status=row["status"],
            order_date=order_date,
            today=today,
            received_date=parsed_received,
            online_purchase=online_purchase,
            special_item=special_item,
        )

        result: dict = {
            "verificado": True,
            "pedido": row["order_id"],
            "motivo_informado": reason,
            "data_pedido": row["order_date"],
            "data_referencia": today.isoformat(),
            **evaluation,
        }

        if row["estimated_delivery"] and received_date is None:
            result["previsao_de_entrega_registrada"] = row["estimated_delivery"]
            result["atencao"] = (
                "Previsão de entrega não é data de recebimento; não use como tal."
            )
        return result
