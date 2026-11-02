import json
import re

import pytest

from emporio.config import get_settings
from emporio.tools.support import handoff_to_human, search_policies, simulate_payment


def test_search_policies_regret():
    result = search_policies("me arrependi, posso devolver?")
    assert result["trechos"]
    assert result["trechos"][0]["secao"].startswith("4. Política de Trocas")
    assert "4.1" in result["trechos"][0]["secao"]


def test_simulate_single_promo_item():
    result = simulate_payment(items=[{"produto_id": 121, "quantidade": 1}])
    assert result["valor_base"] == "R$ 439,20"
    assert result["pix"]["desconto_aplicado"] is False


def test_simulate_mixed_items_pix_partial():
    result = simulate_payment(
        items=[
            {"produto_id": 121, "quantidade": 1},
            {"produto_id": 81, "quantidade": 2},
        ]
    )
    assert result["pix"]["total"] == "R$ 1.579,01"
    assert "só nos itens sem promoção" in result["pix"]["observacao"]


def test_simulate_hypothetical_amount():
    result = simulate_payment(amount=439.2)
    assert result["simulacao_hipotetica"] is True
    assert result["pix"]["total"] is None


def test_simulate_installments_not_allowed():
    result = simulate_payment(items=[{"produto_id": 81, "quantidade": 1}], installments=10)
    assert result["parcelamento_pedido"]["permitido"] is False
    assert result["parcelamento_pedido"]["max_parcelas_sem_juros"] == 6


def test_simulate_unavailable_product_warning():
    result = simulate_payment(items=[{"produto_id": 96, "quantidade": 1}])
    assert any("não está disponível" in aviso for aviso in result["avisos"])


def test_simulate_quantity_over_stock_hides_number():
    result = simulate_payment(items=[{"produto_id": 81, "quantidade": 999}])
    aviso = next(a for a in result["avisos"] if "maior que o estoque" in a)
    # Não revela a quantidade pedida nem o número de unidades em estoque.
    assert "999" not in aviso
    assert aviso == "Quantidade pedida de Yamaha C40 Nylon Natural maior que o estoque disponível."


def test_simulate_nonexistent_product():
    result = simulate_payment(items=[{"produto_id": 999999, "quantidade": 1}])
    assert "erro" in result


def test_simulate_no_input():
    assert "erro" in simulate_payment()


def test_handoff_protocol_format_and_persistence():
    result = handoff_to_human("reclamacao", "Cliente insatisfeito", thread_id="t-aaa")
    assert re.match(r"^EM-\d{8}-[0-9A-F]{6}$", result["protocolo"])

    path = get_settings().handoffs_file
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    assert any(json.loads(line)["protocolo"] == result["protocolo"] for line in lines)


def test_handoff_idempotent_same_thread_and_reason():
    path = get_settings().handoffs_file
    before = len(path.read_text(encoding="utf-8").splitlines()) if path.exists() else 0

    first = handoff_to_human("cancelamento", "resumo", thread_id="t-idem")
    mid = len(path.read_text(encoding="utf-8").splitlines())
    second = handoff_to_human("cancelamento", "resumo de novo", thread_id="t-idem")
    after = len(path.read_text(encoding="utf-8").splitlines())

    assert second["protocolo"] == first["protocolo"]
    assert second["ja_registrado"] is True
    assert after == mid  # não gravou de novo
    assert mid == before + 1


def test_handoff_different_thread_new_protocol():
    first = handoff_to_human("reclamacao", "a", thread_id="t-x1")
    second = handoff_to_human("reclamacao", "b", thread_id="t-x2")
    assert first["protocolo"] != second["protocolo"]


def test_handoff_invalid_reason():
    with pytest.raises(ValueError):
        handoff_to_human("outro_motivo", "resumo")
