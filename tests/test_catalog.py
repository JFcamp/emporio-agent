from emporio.tools import catalog


def test_search_by_category_and_max_price():
    result = catalog.search_products(category="violão", max_price=1000)
    assert result["filtros"]["categoria"] == "Violões"
    produtos = result["produtos"]
    assert produtos
    assert all(p["disponibilidade"] == "em estoque" for p in produtos)
    precos = [_to_float(p["preco"]) for p in produtos]
    assert all(preco <= 1000 for preco in precos)
    assert precos == sorted(precos)


def test_search_les_paul_exact():
    result = catalog.search_products("les paul")
    assert [p["nome"] for p in result["produtos"]] == ["Gibson Les Paul Standard '50s"]


def test_search_seven_strings_excludes_six():
    result = catalog.search_products("7 cordas")
    for p in result["produtos"]:
        assert "6 Cordas" not in p["nome"]
    assert result["total_encontrado"] >= 1


def test_search_empty_category():
    result = catalog.search_products(category="Cordas Orquestrais")
    assert result["total_encontrado"] == 0
    assert "não há nenhum item" in result["observacao"]


def test_search_unknown_category():
    result = catalog.search_products(category="flauta doce xyz")
    assert "erro" in result
    assert "categorias" in result
    assert len(result["categorias"]) == 9


def test_only_available_filter():
    incluido = catalog.search_products(only_available=False, limit=100)
    ids_incluidos = {p["id"] for p in incluido["produtos"]}
    assert 96 in ids_incluidos

    padrao = catalog.search_products(limit=100)
    ids_padrao = {p["id"] for p in padrao["produtos"]}
    assert 96 not in ids_padrao


def test_limit_observation():
    result = catalog.search_products(limit=2)
    assert len(result["produtos"]) == 2
    assert "Mostrando 2 de" in result["observacao"]


def test_get_details_by_name():
    result = catalog.get_product_details("Takamine GD20")
    assert result["id"] == 95
    assert result["preco"] == "R$ 2.199,00"


def test_get_details_ambiguous():
    result = catalog.get_product_details("Takamine")
    assert result["encontrado"] is False
    assert len(result["candidatos"]) >= 2


def test_get_details_out_of_stock_has_alternatives():
    result = catalog.get_product_details("96")
    assert result["disponibilidade"] == "esgotado no momento"
    alternativas = result["alternativas_disponiveis"]
    assert alternativas
    assert all(a["disponibilidade"] == "em estoque" for a in alternativas)
    assert all(a["categoria"] == result["categoria"] for a in alternativas)


def test_get_details_discontinued_and_coming_soon():
    descontinuado = catalog.get_product_details("136")
    assert descontinuado["disponibilidade"].startswith("descontinuado")
    em_breve = catalog.get_product_details("130")
    assert em_breve["disponibilidade"].startswith("em breve")


def test_get_details_not_found():
    result = catalog.get_product_details("produto que não existe xyz123")
    assert result["encontrado"] is False
    assert "não encontrado" in result["mensagem"].lower()


def test_active_promotions():
    result = catalog.list_active_promotions()
    ids = {p["id"] for p in result["promocoes_ativas"]}
    assert ids == {90, 94, 121, 127}
    prod_121 = next(p for p in result["promocoes_ativas"] if p["id"] == 121)
    assert prod_121["promocao"]["preco_original"] == "R$ 549,00"
    assert prod_121["promocao"]["desconto"] == "20%"
    assert prod_121["promocao"]["preco_promocional"] == "R$ 439,20"


def test_summary_never_exposes_stock():
    result = catalog.search_products(limit=100, only_available=False)
    for produto in result["produtos"]:
        assert "stock_quantity" not in produto
        assert "estoque" not in produto


def test_list_categories():
    categorias = catalog.list_categories()
    assert len(categorias) == 9
    por_nome = {c["categoria"]: c["produtos_ativos"] for c in categorias}
    assert por_nome["Instrumentos de Sopro (Madeiras)"] == 0
    assert por_nome["Instrumentos de Sopro (Metais)"] == 0
    assert por_nome["Cordas Orquestrais"] == 0


def _to_float(brl_value: str) -> float:
    cleaned = brl_value.replace("R$", "").strip().replace(".", "").replace(",", ".")
    return float(cleaned)
