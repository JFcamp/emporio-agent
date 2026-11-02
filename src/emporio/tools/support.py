"""Ferramentas de apoio: políticas, simulação de pagamento e encaminhamento.

Simulação de pagamento trabalha em centavos inteiros e nunca revela a
quantidade exata de estoque. O encaminhamento grava um registro local (protótipo)
com protocolo, de forma idempotente por thread_id + motivo no mesmo dia.
"""

import json
import uuid
from datetime import datetime

from emporio.config import STORE_TZ, get_settings
from emporio.data.db import connect
from emporio.domain.payments import (
    check_installments,
    from_cents,
    payment_options,
    to_cents,
)
from emporio.policies.retriever import get_retriever
from emporio.utils import brl

VALID_HANDOFF_REASONS = ("reclamacao", "cancelamento", "caso_nao_coberto", "pedido_do_cliente")


def search_policies(question: str) -> dict:
    results = get_retriever().search(question)
    if not results:
        return {"trechos": [], "mensagem": "Nada encontrado no manual sobre isso."}
    return {"trechos": [{"secao": r["section"], "texto": r["text"]} for r in results]}


def _simulate_by_items(items: list[dict]) -> dict | tuple[dict, int]:
    with connect() as conn:
        total_cents = 0
        pix_eligible_cents = 0
        linhas: list[dict] = []
        avisos: list[str] = []

        for item in items:
            product_id = item.get("produto_id")
            quantity = item.get("quantidade", 1)
            if quantity < 1:
                return {"erro": f"Quantidade inválida para o produto {product_id}."}

            row = conn.execute(
                "SELECT * FROM v_catalog WHERE product_id = ?", (product_id,)
            ).fetchone()
            if row is None:
                return {"erro": f"Produto {product_id} não encontrado no catálogo."}

            unit_cents = to_cents(row["final_price_brl"])
            subtotal = unit_cents * quantity
            total_cents += subtotal

            in_promo = row["discount_percent"] is not None
            if not in_promo:
                pix_eligible_cents += subtotal

            linhas.append(
                {
                    "produto": row["name"],
                    "quantidade": quantity,
                    "preco_unitario": brl(from_cents(unit_cents)),
                    "em_promocao": in_promo,
                }
            )

            if not row["is_available"]:
                avisos.append(f"{row['name']} não está disponível para compra.")
            elif quantity > row["stock_quantity"]:
                avisos.append(
                    f"Quantidade pedida de {row['name']} maior que o estoque disponível."
                )

        options = payment_options(total_cents, pix_eligible_cents)
        if 0 < pix_eligible_cents < total_cents:
            options["pix"]["observacao"] = (
                "Desconto de 5% aplicado só nos itens sem promoção."
            )

        result: dict = {"itens": linhas, **options}
        if avisos:
            result["avisos"] = avisos
        return result, total_cents


def simulate_payment(
    items: list[dict] | None = None,
    amount: float | None = None,
    installments: int | None = None,
) -> dict:
    if items:
        simulated = _simulate_by_items(items)
        if isinstance(simulated, dict):  # erro
            return simulated
        result, total_cents = simulated
    elif amount is not None and amount > 0:
        total_cents = to_cents(amount)
        result = {"simulacao_hipotetica": True, **payment_options(total_cents, None)}
    else:
        return {"erro": "Informe os produtos (id e quantidade) ou um valor positivo."}

    if installments is not None:
        result["parcelamento_pedido"] = check_installments(total_cents, installments)
    return result


def _handoff_records() -> list[dict]:
    path = get_settings().handoffs_file
    if not path.exists():
        return []
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            records.append(json.loads(line))
    return records


def handoff_to_human(
    reason: str,
    summary: str,
    customer_contact: str | None = None,
    thread_id: str | None = None,
) -> dict:
    if reason not in VALID_HANDOFF_REASONS:
        raise ValueError(f"Motivo de encaminhamento inválido: {reason}")

    now = datetime.now(STORE_TZ)
    today_str = now.date().isoformat()

    # Idempotência: mesma conversa + mesmo motivo no mesmo dia reusa o protocolo.
    if thread_id is not None:
        for record in _handoff_records():
            if (
                record.get("conversa") == thread_id
                and record.get("motivo") == reason
                and record.get("criado_em", "").startswith(today_str)
            ):
                return {
                    "protocolo": record["protocolo"],
                    "ja_registrado": True,
                    "prazo_retorno": "até 24 horas úteis",
                    "mensagem": (
                        "Solicitação registrada para a equipe. O registro é local "
                        "neste protótipo."
                    ),
                }

    protocol = f"EM-{now.strftime('%Y%m%d')}-{uuid.uuid4().hex[:6].upper()}"
    record = {
        "protocolo": protocol,
        "criado_em": now.isoformat(),
        "motivo": reason,
        "resumo": summary,
        "contato": customer_contact,
        "conversa": thread_id,
    }

    path = get_settings().handoffs_file
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "protocolo": protocol,
        "prazo_retorno": "até 24 horas úteis",
        "mensagem": "Solicitação registrada para a equipe. O registro é local neste protótipo.",
    }
