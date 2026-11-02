import pytest

from emporio.policies.retriever import get_retriever

# Cada caso: (consulta, verificador do id esperado). O verificador recebe um id
# e diz se ele é aceitável, permitindo casos com mais de um alvo válido.
CASES = [
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


@pytest.mark.parametrize("query, is_expected", CASES)
def test_expected_in_top3(query, is_expected):
    retriever = get_retriever()
    top3 = [result["id"] for result in retriever.search(query, k=4)[:3]]
    assert any(is_expected(i) for i in top3), f"{query} -> {top3}"


def test_hit_at_1_above_threshold():
    retriever = get_retriever()
    hits = 0
    for query, is_expected in CASES:
        results = retriever.search(query, k=4)
        if results and is_expected(results[0]["id"]):
            hits += 1
    hit_at_1 = hits / len(CASES)
    assert hit_at_1 >= 0.7, f"hit@1={hit_at_1:.3f}"
