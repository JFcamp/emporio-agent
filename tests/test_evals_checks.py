from evals.checks import brl_format_ok, check_turn, normalize_reply, subset_match

FALLBACK = "Tive um probleminha técnico aqui."


def test_subset_match_nested_dict():
    assert subset_match({"a": {"b": 1}}, {"a": {"b": 1, "c": 2}, "d": 3})
    assert not subset_match({"a": {"b": 2}}, {"a": {"b": 1}})


def test_subset_match_list_items():
    assert subset_match({"itens": [{"id": 1}]}, {"itens": [{"id": 1, "q": 2}, {"id": 9}]})
    assert not subset_match({"itens": [{"id": 5}]}, {"itens": [{"id": 1}]})


def test_subset_match_strings_normalized():
    assert subset_match("Violões", "violoes")
    assert not subset_match("Violão", "guitarra")


def test_brl_format_ok():
    assert brl_format_ok("Custa R$ 1.234,56 à vista")
    assert not brl_format_ok("Custa R$429,90")
    assert not brl_format_ok("Custa R$ 1234,56")


def test_normalize_reply_treats_rs_equal():
    assert normalize_reply("R$ 439,20") == normalize_reply("r$439,20")


def _calls(*pairs):
    return [{"name": n, "args": a} for n, a in pairs]


def test_check_turn_tools_all_pass_and_fail():
    calls = _calls(("buscar_produtos", {}))
    assert check_turn({"tools_all": ["buscar_produtos"]}, "ok", calls, FALLBACK) == []
    assert check_turn({"tools_all": ["detalhar_produto"]}, "ok", calls, FALLBACK)


def test_check_turn_tools_any_and_none():
    assert check_turn({"tools_any": ["a", "b"]}, "ok", _calls(("b", {})), FALLBACK) == []
    assert check_turn({"tools_none": ["x"]}, "ok", _calls(("y", {})), FALLBACK) == []
    assert check_turn({"tools_none": ["x"]}, "ok", _calls(("x", {})), FALLBACK)


def test_check_turn_args_and_args_absent():
    calls = _calls(("simular_pagamento", {"itens": [{"produto_id": 81, "quantidade": 1}]}))
    assert check_turn(
        {"args": [{"tool": "simular_pagamento", "match": {"itens": [{"produto_id": 81}]}}]},
        "ok", calls, FALLBACK,
    ) == []
    assert check_turn(
        {"args_absent": [{"tool": "simular_pagamento", "keys": ["valor"]}]},
        "ok", calls, FALLBACK,
    ) == []
    with_valor = _calls(("simular_pagamento", {"valor": 100}))
    assert check_turn(
        {"args_absent": [{"tool": "simular_pagamento", "keys": ["valor"]}]},
        "ok", with_valor, FALLBACK,
    )


def test_check_turn_contains_variants():
    assert check_turn({"contains_all": ["439,20"]}, "sai por R$ 439,20", [], FALLBACK) == []
    assert check_turn({"contains_all": ["999"]}, "sai por R$ 439,20", [], FALLBACK)
    assert check_turn({"contains_any": ["a", "promo"]}, "tem promoção sim", [], FALLBACK) == []
    assert check_turn({"not_contains": ["grátis"]}, "não é gratis", [], FALLBACK)


def test_check_turn_contains_any_groups():
    text = "está esgotado, veja o Shelby SGD-195E"
    expect = {"contains_any": [["esgotado", "acabou"], ["shelby sgd-195e", "yamaha c70"]]}
    assert check_turn(expect, text, [], FALLBACK) == []
    expect_fail = {"contains_any": [["esgotado"], ["produto inexistente"]]}
    assert check_turn(expect_fail, text, [], FALLBACK)


def test_check_turn_brl_and_fallback():
    assert check_turn({}, "R$429,90", [], FALLBACK)  # brl_format padrão True
    assert check_turn({}, FALLBACK, [], FALLBACK)  # no_fallback padrão True
    assert check_turn({"no_fallback": False, "brl_format": False}, FALLBACK, [], FALLBACK) == []
