import csv
import json
import sqlite3
from pathlib import Path

from emporio.config import Settings, get_settings
from emporio.utils import normalize, normalize_phone

SCHEMA = """
CREATE TABLE categories (
    category_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(category_id),
    price_brl REAL NOT NULL,
    description TEXT,
    stock_quantity INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('active', 'discontinued', 'coming_soon')),
    specs_json TEXT,
    created_at TEXT,
    search_text TEXT NOT NULL
);

CREATE TABLE promotions (
    promotion_id INTEGER PRIMARY KEY,
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    discount_percent REAL NOT NULL,
    description TEXT,
    is_active INTEGER NOT NULL
);

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT,
    phone_digits TEXT,
    email TEXT,
    city TEXT
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER NOT NULL REFERENCES customers(customer_id),
    order_date TEXT NOT NULL,
    status TEXT NOT NULL,
    total_brl REAL NOT NULL,
    payment_method TEXT,
    tracking_code TEXT,
    estimated_delivery TEXT,
    notes TEXT
);

CREATE TABLE order_items (
    order_id INTEGER NOT NULL REFERENCES orders(order_id),
    product_id INTEGER NOT NULL REFERENCES products(product_id),
    quantity INTEGER NOT NULL
);
"""

CREATE_CATALOG_VIEW = """
CREATE VIEW v_catalog AS
WITH ranked_promotions AS (
    SELECT
        product_id,
        discount_percent,
        description AS promo_name,
        ROW_NUMBER() OVER (
            PARTITION BY product_id
            ORDER BY discount_percent DESC, promotion_id
        ) AS rn
    FROM promotions
    WHERE is_active = 1
),
best_promotion AS (
    SELECT product_id, discount_percent, promo_name
    FROM ranked_promotions
    WHERE rn = 1
)
SELECT
    p.product_id,
    p.name,
    p.category_id,
    c.name AS category,
    p.price_brl,
    p.description,
    p.stock_quantity,
    p.status,
    p.specs_json,
    p.search_text,
    (p.status = 'active' AND p.stock_quantity > 0) AS is_available,
    bp.discount_percent,
    bp.promo_name,
    ROUND(p.price_brl * (1 - COALESCE(bp.discount_percent, 0) / 100.0), 2) AS final_price_brl
FROM products p
JOIN categories c ON c.category_id = p.category_id
LEFT JOIN best_promotion bp ON bp.product_id = p.product_id;
"""


def _read_csv(path: Path) -> list[dict[str, str | None]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, str | None]] = []
        for raw_row in reader:
            row: dict[str, str | None] = {}
            for key, value in raw_row.items():
                clean_key = key.strip() if key is not None else key
                clean_value = value.strip() if isinstance(value, str) else value
                row[clean_key] = clean_value if clean_value else None
            rows.append(row)
    return rows


def _to_int(value: str | None) -> int | None:
    return int(value) if value is not None else None


def _to_float(value: str | None) -> float | None:
    return float(value) if value is not None else None


def _load_categories(conn: sqlite3.Connection, rows: list[dict[str, str | None]]) -> None:
    conn.executemany(
        "INSERT INTO categories (category_id, name, description) VALUES (?, ?, ?)",
        [(_to_int(r["category_id"]), r["name"], r["description"]) for r in rows],
    )


def _load_products(
    conn: sqlite3.Connection,
    rows: list[dict[str, str | None]],
    category_names: dict[int, str],
    problems: list[dict[str, str]],
) -> None:
    records = []
    for r in rows:
        product_id = _to_int(r["product_id"])
        category_id = _to_int(r["category_id"])
        specs_raw = r["specs"]
        specs_values: list[str] = []
        specs_json = "{}"
        if specs_raw is not None:
            try:
                parsed = json.loads(specs_raw)
                specs_json = json.dumps(parsed, ensure_ascii=False)
                specs_values = [str(v) for v in parsed.values()]
            except (json.JSONDecodeError, ValueError):
                problems.append(
                    {
                        "tipo": "specs_invalido",
                        "detalhe": f"Produto {product_id} tem specs em JSON inválido.",
                        "decisao": "Gravar specs vazio ({}) e seguir com os demais campos.",
                    }
                )
        category_name = category_names.get(category_id, "") if category_id is not None else ""
        search_text = normalize(
            " ".join(
                part
                for part in [r["name"], category_name, r["description"], *specs_values]
                if part
            )
        )
        records.append(
            (
                product_id,
                r["name"],
                category_id,
                _to_float(r["price_brl"]),
                r["description"],
                _to_int(r["stock_quantity"]),
                r["status"],
                specs_json,
                r["created_at"],
                search_text,
            )
        )
    conn.executemany(
        """
        INSERT INTO products (
            product_id, name, category_id, price_brl, description,
            stock_quantity, status, specs_json, created_at, search_text
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        records,
    )


def _load_promotions(conn: sqlite3.Connection, rows: list[dict[str, str | None]]) -> None:
    conn.executemany(
        """
        INSERT INTO promotions (promotion_id, product_id, discount_percent, description, is_active)
        VALUES (?, ?, ?, ?, ?)
        """,
        [
            (
                _to_int(r["promotion_id"]),
                _to_int(r["product_id"]),
                _to_float(r["discount_percent"]),
                r["description"],
                _to_int(r["is_active"]),
            )
            for r in rows
        ],
    )


def _load_customers(conn: sqlite3.Connection, rows: list[dict[str, str | None]]) -> None:
    records = []
    for r in rows:
        email = r["email"]
        email = email.replace(" ", "").lower() if email is not None else None
        records.append(
            (
                _to_int(r["customer_id"]),
                r["name"],
                r["phone"],
                normalize_phone(r["phone"]) or None,
                email,
                r["city"],
            )
        )
    conn.executemany(
        """
        INSERT INTO customers (customer_id, name, phone, phone_digits, email, city)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        records,
    )


def _load_orders(conn: sqlite3.Connection, rows: list[dict[str, str | None]]) -> None:
    conn.executemany(
        """
        INSERT INTO orders (
            order_id, customer_id, order_date, status, total_brl,
            payment_method, tracking_code, estimated_delivery, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                _to_int(r["order_id"]),
                _to_int(r["customer_id"]),
                r["order_date"],
                r["status"],
                _to_float(r["total_brl"]),
                r["payment_method"],
                r["tracking_code"],
                r["estimated_delivery"],
                r["notes"],
            )
            for r in rows
        ],
    )


def _load_order_items(conn: sqlite3.Connection, rows: list[dict[str, str | None]]) -> None:
    conn.executemany(
        "INSERT INTO order_items (order_id, product_id, quantity) VALUES (?, ?, ?)",
        [
            (_to_int(r["order_id"]), _to_int(r["product_id"]), _to_int(r["quantity"]))
            for r in rows
        ],
    )


def _collect_problems(conn: sqlite3.Connection, problems: list[dict[str, str]]) -> None:
    # Estoque x status: a disponibilidade real pode divergir do campo status.
    for row in conn.execute(
        "SELECT product_id, status, stock_quantity FROM products ORDER BY product_id"
    ):
        status = row["status"]
        stock = row["stock_quantity"]
        product_id = row["product_id"]
        if status == "active" and stock <= 0:
            problems.append(
                {
                    "tipo": "estoque_vs_status",
                    "detalhe": f"Produto {product_id} está ativo mas com estoque {stock}.",
                    "decisao": "Tratar como indisponível e sugerir alternativas.",
                }
            )
        elif status == "discontinued" and stock > 0:
            problems.append(
                {
                    "tipo": "estoque_vs_status",
                    "detalhe": f"Produto {product_id} está descontinuado mas com estoque {stock}.",
                    "decisao": "O status prevalece: não é vendido.",
                }
            )
        elif status == "coming_soon":
            problems.append(
                {
                    "tipo": "estoque_vs_status",
                    "detalhe": f"Produto {product_id} é um lançamento (coming_soon).",
                    "decisao": "Ainda não é vendido.",
                }
            )

    for row in conn.execute(
        """
        SELECT c.category_id, c.name
        FROM categories c
        LEFT JOIN products p ON p.category_id = c.category_id
        WHERE p.product_id IS NULL
        ORDER BY c.category_id
        """
    ):
        problems.append(
            {
                "tipo": "categoria_vazia",
                "detalhe": f"Categoria {row['category_id']} ({row['name']}) não tem produtos.",
                "decisao": "Informar que não há itens no momento.",
            }
        )

    for row in conn.execute(
        """
        SELECT product_id,
               COUNT(*) AS total,
               SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS ativas
        FROM promotions
        GROUP BY product_id
        HAVING COUNT(*) > 1
        ORDER BY product_id
        """
    ):
        problems.append(
            {
                "tipo": "promocao_repetida",
                "detalhe": (
                    f"Produto {row['product_id']} tem {row['total']} promoções cadastradas, "
                    f"{row['ativas']} ativa(s)."
                ),
                "decisao": "Só promoções ativas valem; havendo mais de uma, vale o maior desconto.",
            }
        )

    for row in conn.execute(
        """
        SELECT email, GROUP_CONCAT(customer_id) AS ids, COUNT(*) AS total
        FROM customers
        WHERE email IS NOT NULL
        GROUP BY email
        HAVING COUNT(*) > 1
        ORDER BY email
        """
    ):
        problems.append(
            {
                "tipo": "cliente_duplicado",
                "detalhe": f"E-mail {row['email']} aparece nos clientes {row['ids']}.",
                "decisao": "Manter ambos; a verificação compara com o dono do pedido.",
            }
        )

    # Total divergente: compara o total gravado com a soma dos itens pelo preço atual.
    for row in conn.execute(
        """
        SELECT o.order_id, o.total_brl,
               SUM(oi.quantity * p.price_brl) AS soma_itens
        FROM orders o
        JOIN order_items oi ON oi.order_id = o.order_id
        JOIN products p ON p.product_id = oi.product_id
        GROUP BY o.order_id, o.total_brl
        HAVING ABS(o.total_brl - SUM(oi.quantity * p.price_brl)) > 0.01
        ORDER BY o.order_id
        """
    ):
        problems.append(
            {
                "tipo": "total_divergente",
                "detalhe": (
                    f"Pedido {row['order_id']}: total {row['total_brl']} difere da soma dos "
                    f"itens {round(row['soma_itens'], 2)}."
                ),
                "decisao": "Vale o total do pedido, valor efetivamente cobrado.",
            }
        )


def build(raw_dir: Path | None = None, db_path: Path | None = None) -> dict:
    settings: Settings = get_settings()
    raw_dir = raw_dir or settings.raw_dir
    db_path = db_path or settings.catalog_db

    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    categories = _read_csv(raw_dir / "categories.csv")
    products = _read_csv(raw_dir / "products.csv")
    promotions = _read_csv(raw_dir / "promotions.csv")
    customers = _read_csv(raw_dir / "customers.csv")
    orders = _read_csv(raw_dir / "orders.csv")
    order_items = _read_csv(raw_dir / "order_items.csv")

    problems: list[dict[str, str]] = []
    category_names = {_to_int(r["category_id"]): r["name"] for r in categories}

    conn = sqlite3.connect(db_path)
    try:
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.executescript(SCHEMA)
        _load_categories(conn, categories)
        _load_products(conn, products, category_names, problems)
        _load_promotions(conn, promotions)
        _load_customers(conn, customers)
        _load_orders(conn, orders)
        _load_order_items(conn, order_items)
        conn.executescript(CREATE_CATALOG_VIEW)
        _collect_problems(conn, problems)
        conn.commit()
    finally:
        conn.close()

    report = {
        "contagens": {
            "categorias": len(categories),
            "produtos": len(products),
            "promocoes": len(promotions),
            "clientes": len(customers),
            "pedidos": len(orders),
            "itens": len(order_items),
        },
        "problemas": problems,
    }

    settings.data_quality_json.parent.mkdir(parents=True, exist_ok=True)
    settings.data_quality_json.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return report


def main() -> None:
    settings = get_settings()
    report = build()
    print(f"Banco gerado em: {settings.catalog_db}")
    print("Contagens:")
    for name, count in report["contagens"].items():
        print(f"  {name}: {count}")
    print(f"Problemas registrados: {len(report['problemas'])}")


if __name__ == "__main__":
    main()
