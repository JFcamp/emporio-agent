import pytest

from emporio.policies.retriever import get_retriever

# TUNING_CASES: usados para calibrar SYNONYMS/STOPWORDS. Cada caso é
# (consulta, verificador do id esperado). O verificador aceita mais de um alvo.
TUNING_CASES = [
    ("me arrependi da compra, posso devolver?", lambda i: i == "4.1"),
    ("qual o horário de sábado?", lambda i: i == "2"),
    ("posso parcelar em 10 vezes?", lambda i: i == "3.1"),
    ("qual o endereço da loja?", lambda i: i == "1.2"),
    ("quanto tempo demora a entrega para Dourados?", lambda i: i in {"5.1", "5.2"}),
    ("meu violão veio com defeito", lambda i: i == "4.2"),
    ("como rastrear meu pedido?", lambda i: i == "5.3"),
    ("pix tem desconto em produto que está em promoção?", lambda i: i == "6.2"),
    ("qual a garantia do fabricante?", lambda i: i.startswith("8.")),
    ("quero trocar por outra cor", lambda i: i == "4.3"),
    ("vocês vendem cordas e palhetas?", lambda i: i == "1"),
    ("meus dados pessoais ficam seguros?", lambda i: i == "9"),
]

# HOLDOUT_CASES: perguntas novas, nunca usadas para ajustar o dicionário.
# Servem só para medir generalização.
HOLDOUT_CASES = [
    ("o frete tem seguro?", lambda i: i == "5.2"),
    ("e se o instrumento chegar amassado?", lambda i: i == "5.2"),
    ("vocês vendem pedal de guitarra?", lambda i: i in {"1", "7.1"}),
    ("posso pagar metade no pix e metade no cartão?", lambda i: i == "3.1"),
    ("o que a garantia não cobre?", lambda i: i == "8.3"),
    ("violão com regulagem especial pode ser trocado?", lambda i: i == "4.4"),
    ("vocês abrem em feriado?", lambda i: i == "2"),
    ("quanto custa a entrega aqui em Campo Grande?", lambda i: i == "5.1"),
    ("posso pedir para apagarem meus dados?", lambda i: i == "9"),
    ("o reembolso cai em quantos dias?", lambda i: i == "4.1"),
]


def _metrics(cases):
    retriever = get_retriever()
    hit1 = 0
    hit3 = 0
    details = []
    for query, is_expected in cases:
        results = retriever.search(query, k=4)
        top_ids = [r["id"] for r in results]
        top3 = top_ids[:3]
        ok1 = bool(top_ids) and is_expected(top_ids[0])
        ok3 = any(is_expected(i) for i in top3)
        hit1 += int(ok1)
        hit3 += int(ok3)
        details.append((query, top3, ok3))
    total = len(cases)
    return hit1 / total, hit3 / total, details


@pytest.mark.parametrize("query, is_expected", TUNING_CASES)
def test_tuning_expected_in_top3(query, is_expected):
    retriever = get_retriever()
    top3 = [result["id"] for result in retriever.search(query, k=4)[:3]]
    assert any(is_expected(i) for i in top3), f"{query} -> {top3}"


def test_tuning_hit_at_1_above_threshold():
    hit1, hit3, _ = _metrics(TUNING_CASES)
    print(f"\n[TUNING] hit@1={hit1:.3f} hit@3={hit3:.3f} (n={len(TUNING_CASES)})")
    assert hit1 >= 0.7, f"hit@1={hit1:.3f}"


def test_holdout_generalizes():
    hit1, hit3, details = _metrics(HOLDOUT_CASES)
    print(f"\n[HOLDOUT] hit@1={hit1:.3f} hit@3={hit3:.3f} (n={len(HOLDOUT_CASES)})")
    for query, top3, ok3 in details:
        flag = "OK " if ok3 else "XX "
        print(f"  {flag} {top3} | {query}")
    assert hit3 >= 0.8, f"holdout hit@3={hit3:.3f}"
