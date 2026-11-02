import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from emporio.config import get_settings


@contextmanager
def connect(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or get_settings().catalog_db
    if not path.exists():
        raise FileNotFoundError(
            f"Banco de dados não encontrado em {path}. "
            "Rode `python -m emporio.bootstrap` para gerar os dados."
        )

    conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
