"""Consultas de catálogo para o agente.

Lê exclusivamente a view v_catalog pelo banco em modo somente leitura, com SQL
parametrizado. Retorna dicts prontos para o LLM, com dinheiro formatado por
brl(). A quantidade exata de estoque nunca é exposta — só rótulos de
disponibilidade e, no máximo, o aviso de "últimas unidades".

Esta camada não importa LangChain: o contrato das ferramentas com o LLM é
montado numa etapa posterior.
"""

import json
import sqlite3

from rapidfuzz import fuzz, process

from emporio.data.db import connect
from emporio.utils import brl, normalize

AVAILABILITY_LABELS = {
    "em_estoque": "em estoque",
    "esgotado": "esgotado no momento",
    "descontinuado": "descontinuado (não faz mais parte do catálogo)",
    "em_breve": "em breve (lançamento, ainda não disponível para compra)",
}

QUERY_STOPWORDS = {"de", "da", "do", "com", "para", "ate", "e", "o", "a", "um", "uma", "em"}

LOW_STOCK_THRESHOLD = 2


def _availability_label(status: str, stock_quantity: int) -> str:
    if status == "discontinued":
        return AVAILABILITY_LABELS["descontinuado"]
    if status == "coming_soon":
        return AVAILABILITY_LABELS["em_breve"]
    if status == "active" and stock_quantity > 0:
        return AVAILABILITY_LABELS["em_estoque"]
    return AVAILABILITY_LABELS["esgotado"]


def product_summary(row: sqlite3.Row) -> dict:
    status = row["status"]
    stock = row["stock_quantity"]
    summary = {
        "id": row["product_id"],
        "nome": row["name"],
        "categoria": row["category"],
        "preco": brl(row["price_brl"]),
        "disponibilidade": _availability_label(status, stock),
    }

    if row["discount_percent"] is not None:
        discount = row["discount_percent"]
        discount_label = f"{discount:g}%"
        summary["promocao"] = {
            "nome": row["promo_name"],
            "desconto": discount_label,
            "preco_original": brl(row["price_brl"]),
            "preco_promocional": brl(row["final_price_brl"]),
        }

    if status == "active" and 0 < stock <= LOW_STOCK_THRESHOLD:
        summary["aviso"] = "últimas unidades"

    return summary


def _query_terms(term: str) -> list[str]:
    tokens = normalize(term).split()
    return [t for t in tokens if t not in QUERY_STOPWORDS]


def _token_matches(query_term: str, token: str) -> bool:
    if query_term.isdigit() or token.isdigit():
        return query_term == token
    if query_term == token:
        return True
    if len(query_term) >= 4 and len(token) >= 4 and (
        query_term.startswith(token) or token.startswith(query_term)
    ):
        return True
    if len(query_term) >= 5 and fuzz.ratio(query_term, token) >= 80:
        return True
    return False


def term_score(term: str, search_text: str) -> float:
    query_terms = _query_terms(term)
    if not query_terms:
        return 1.0
    tokens = search_text.split()
    matched = sum(1 for qt in query_terms if any(_token_matches(qt, tok) for tok in tokens))
    return matched / len(query_terms)


def resolve_category(conn: sqlite3.Connection, text: str) -> tuple[int, str] | None:
    rows = conn.execute("SELECT category_id, name FROM categories").fetchall()
    choices = {normalize(row["name"]): (row["category_id"], row["name"]) for row in rows}
    match = process.extractOne(normalize(text), choices.keys(), scorer=fuzz.WRatio, score_cutoff=70)
    if match is None:
        return None
    return choices[match[0]]


def _category_names(conn: sqlite3.Connection) -> list[str]:
    return [row["name"] for row in conn.execute("SELECT name FROM categories ORDER BY category_id")]


def _category_is_empty(conn: sqlite3.Connection, category_id: int) -> bool:
    # Categoria sem NENHUM produto cadastrado (independe de filtros da busca).
    row = conn.execute(
        "SELECT COUNT(*) AS total FROM products WHERE category_id = ?", (category_id,)
    ).fetchone()
    return row["total"] == 0


def search_products(
    term: str | None = None,
    category: str | None = None,
    max_price: float | None = None,
    min_price: float | None = None,
    only_available: bool = True,
    limit: int = 8,
) -> dict:
    with connect() as conn:
        category_name: str | None = None
        category_id: int | None = None
        if category is not None:
            resolved = resolve_category(conn, category)
            if resolved is None:
                return {
                    "erro": f"Categoria '{category}' não encontrada.",
                    "categorias": _category_names(conn),
                }
            category_id, category_name = resolved

        clauses: list[str] = []
        params: list = []
        if category_name is not None:
            clauses.append("category = ?")
            params.append(category_name)
        if only_available:
            clauses.append("is_available = 1")
        if max_price is not None:
            clauses.append("final_price_brl <= ?")
            params.append(max_price)
        if min_price is not None:
            clauses.append("final_price_brl >= ?")
            params.append(min_price)

        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = conn.execute(
            f"SELECT * FROM v_catalog {where} ORDER BY final_price_brl ASC",
            params,
        ).fetchall()

        filtros = {
            "termo": term,
            "categoria": category_name,
            "preco_min": brl(min_price) if min_price is not None else None,
            "preco_max": brl(max_price) if max_price is not None else None,
            "apenas_disponiveis": only_available,
        }

        aviso_busca: str | None = None
        if term:
            scored = [(row, term_score(term, row["search_text"])) for row in rows]
            exact = [row for row, score in scored if score >= 1.0]
            if exact:
                rows = exact
            else:
                rows = [row for row, score in scored if score >= 0.5]
                if rows:
                    aviso_busca = (
                        "Nenhum produto bate com todos os termos; estes são aproximados."
                    )

        total = len(rows)
        result: dict = {
            "filtros": filtros,
            "total_encontrado": total,
            "produtos": [product_summary(row) for row in rows[:limit]],
        }
        if aviso_busca is not None:
            result["aviso_busca"] = aviso_busca
        if total > limit:
            result["observacao"] = f"Mostrando {limit} de {total}. Refine a busca se precisar."
        elif total == 0:
            if category_id is not None and _category_is_empty(conn, category_id):
                result["observacao"] = (
                    f"No momento não há nenhum item de {category_name} no catálogo."
                )
            else:
                result["observacao"] = "Nenhum produto encontrado com esses filtros."

        result["resumo"] = _search_resumo(
            total, limit, category_name, max_price, min_price, result.get("observacao")
        )
        return result


def _search_resumo(
    total: int,
    limit: int,
    category_name: str | None,
    max_price: float | None,
    min_price: float | None,
    observacao: str | None,
) -> str:
    if total == 0:
        return observacao or "Nenhum produto encontrado com esses filtros."

    onde = f"em {category_name}" if category_name else "no catálogo"
    plural = "opção" if total == 1 else "opções"
    frase = f"Encontrei {total} {plural} {onde}"
    if max_price is not None:
        frase += f" até {brl(max_price)}"
    if min_price is not None:
        frase += f" a partir de {brl(min_price)}"
    frase += "."
    if total > limit:
        frase += (
            f" Mostrando as {limit} de menor preço; posso filtrar por faixa de "
            "preço, tipo de corda ou marca."
        )
    return frase


def _row_by_id(conn: sqlite3.Connection, product_id: int) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM v_catalog WHERE product_id = ?", (product_id,)
    ).fetchone()


def _alternatives(conn: sqlite3.Connection, row: sqlite3.Row) -> list[dict]:
    candidates = conn.execute(
        """
        SELECT * FROM v_catalog
        WHERE category_id = ? AND is_available = 1 AND product_id != ?
        """,
        (row["category_id"], row["product_id"]),
    ).fetchall()
    reference = row["final_price_brl"]
    candidates.sort(key=lambda r: abs(r["final_price_brl"] - reference))
    return [product_summary(r) for r in candidates[:3]]


def get_product_details(name_or_id: str) -> dict:
    with connect() as conn:
        text = name_or_id.strip()
        row: sqlite3.Row | None = None

        if text.isdigit():
            row = _row_by_id(conn, int(text))
        else:
            rows = conn.execute("SELECT * FROM v_catalog").fetchall()
            normalized = normalize(text)
            scored = sorted(
                (
                    (row, fuzz.token_set_ratio(normalized, normalize(row["name"])))
                    for row in rows
                ),
                key=lambda item: item[1],
                reverse=True,
            )
            if scored:
                best_row, best_score = scored[0]
                runner_up = scored[1][1] if len(scored) > 1 else 0
                if best_score >= 80 and not (runner_up >= 70 and best_score - runner_up < 5):
                    row = best_row
                else:
                    candidates = [r for r, score in scored if score >= 55]
                    if candidates:
                        return {
                            "encontrado": False,
                            "mensagem": (
                                "Não identifiquei um único produto. Confirme com o "
                                "cliente qual deles."
                            ),
                            "candidatos": [product_summary(r) for r in candidates[:4]],
                        }

        if row is None:
            return {
                "encontrado": False,
                "mensagem": "Produto não encontrado no catálogo da loja.",
            }

        details = product_summary(row)
        details["encontrado"] = True
        details["descricao"] = row["description"]
        details["especificacoes"] = json.loads(row["specs_json"]) if row["specs_json"] else {}

        if not row["is_available"]:
            details["alternativas_disponiveis"] = _alternatives(conn, row)

        return details


def list_active_promotions() -> dict:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM v_catalog
            WHERE discount_percent IS NOT NULL
            ORDER BY discount_percent DESC, product_id
            """
        ).fetchall()
    return {
        "promocoes_ativas": [product_summary(row) for row in rows],
        "regra": "Promoções não acumulam com o desconto de 5% do PIX.",
    }


def list_categories() -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT c.name AS categoria,
                   COUNT(CASE WHEN p.status = 'active' THEN 1 END) AS produtos_ativos
            FROM categories c
            LEFT JOIN products p ON p.category_id = c.category_id
            GROUP BY c.category_id, c.name
            ORDER BY c.category_id
            """
        ).fetchall()
    return [{"categoria": row["categoria"], "produtos_ativos": row["produtos_ativos"]} for row in rows]
