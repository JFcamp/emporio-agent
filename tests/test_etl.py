import json
import sqlite3

import pytest

from emporio.config import get_settings
from emporio.data import etl
from emporio.data.db import connect


def _problems_by_type(report: dict) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = {}
    for problem in report["problemas"]:
        grouped.setdefault(problem["tipo"], []).append(problem)
    return grouped


def test_counts(built_data):
    assert built_data["contagens"] == {
        "categorias": 9,
        "produtos": 65,
        "promocoes": 25,
        "clientes": 50,
        "pedidos": 20,
        "itens": 22,
    }


def test_problem_totals(built_data):
    grouped = _problems_by_type(built_data)
    assert len(built_data["problemas"]) == 12
    assert len(grouped["estoque_vs_status"]) == 3
    assert len(grouped["categoria_vazia"]) == 3
    assert len(grouped["promocao_repetida"]) == 3
    assert len(grouped["cliente_duplicado"]) == 1
    assert len(grouped["total_divergente"]) == 2


def test_problem_targets(built_data):
    grouped = _problems_by_type(built_data)

    estoque = " ".join(p["detalhe"] for p in grouped["estoque_vs_status"])
    assert "Produto 96" in estoque
    assert "Produto 136" in estoque
    assert "Produto 130" in estoque

    categorias = " ".join(p["detalhe"] for p in grouped["categoria_vazia"])
    assert "Categoria 6" in categorias
    assert "Categoria 7" in categorias
    assert "Categoria 8" in categorias

    promo = " ".join(p["detalhe"] for p in grouped["promocao_repetida"])
    assert "Produto 93" in promo
    assert "Produto 96" in promo
    assert "Produto 99" in promo

    duplicado = grouped["cliente_duplicado"][0]["detalhe"]
    assert "11" in duplicado
    assert "43" in duplicado

    totais = " ".join(p["detalhe"] for p in grouped["total_divergente"])
    assert "Pedido 3" in totais
    assert "Pedido 20" in totais


def test_data_quality_json_matches_report(built_data):
    settings = get_settings()
    saved = json.loads(settings.data_quality_json.read_text(encoding="utf-8"))
    assert saved == built_data


def test_is_available(built_data):
    with connect() as conn:
        rows = {
            row["product_id"]: row["is_available"]
            for row in conn.execute(
                "SELECT product_id, is_available FROM v_catalog WHERE product_id IN (96, 136, 130, 95)"
            )
        }
    assert rows[96] == 0
    assert rows[136] == 0
    assert rows[130] == 0
    assert rows[95] == 1


def test_active_promotions_applied(built_data):
    with connect() as conn:
        rows = {
            row["product_id"]: row
            for row in conn.execute(
                "SELECT product_id, discount_percent, final_price_brl FROM v_catalog "
                "WHERE discount_percent IS NOT NULL"
            )
        }
    assert set(rows) == {90, 94, 121, 127}
    assert rows[121]["discount_percent"] == 20.0
    assert rows[121]["final_price_brl"] == 439.2


def test_search_text_normalized(built_data):
    with connect() as conn:
        row = conn.execute(
            "SELECT search_text FROM products WHERE product_id = 95"
        ).fetchone()
    search_text = row["search_text"]
    assert search_text == search_text.lower()
    assert "á" not in search_text
    assert "takamine" in search_text


def test_customer_transforms(built_data):
    with connect() as conn:
        row = conn.execute(
            "SELECT phone_digits, email FROM customers WHERE customer_id = 2"
        ).fetchone()
    assert row["phone_digits"] == "67996547821"
    assert row["email"] == row["email"].lower()


def test_database_is_read_only(built_data):
    with connect() as conn:
        with pytest.raises(sqlite3.OperationalError):
            conn.execute("INSERT INTO categories (category_id, name) VALUES (999, 'x')")


def test_connect_missing_file_raises(tmp_path):
    missing = tmp_path / "nao_existe.db"
    with pytest.raises(FileNotFoundError):
        with connect(missing):
            pass


def test_build_is_idempotent(built_data):
    first = etl.build()
    second = etl.build()
    assert first == second
