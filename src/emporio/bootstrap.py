"""Prepara os artefatos de dados: banco SQLite e índice de políticas.

ensure_data reconstrói sob demanda (banco/índice ausente, force, ou arquivo de
origem mais novo que o artefato), para a CLI e os testes partirem de dados
prontos sem reprocessar à toa.
"""

import json

from emporio.config import get_settings
from emporio.data import etl
from emporio.policies import ingest
from emporio.policies.retriever import get_retriever


def _newest_mtime(*paths) -> float:
    return max((p.stat().st_mtime for p in paths if p.exists()), default=0.0)


def _raw_is_newer(settings, target) -> bool:
    if not target.exists():
        return True
    raw_files = list(settings.raw_dir.glob("*"))
    return _newest_mtime(*raw_files) > target.stat().st_mtime


def ensure_data(force: bool = False) -> None:
    settings = get_settings()

    if force or _raw_is_newer(settings, settings.catalog_db):
        etl.build()

    if force or _raw_is_newer(settings, settings.policies_json):
        ingest.build()
        get_retriever.cache_clear()


def main() -> None:
    settings = get_settings()
    report = etl.build()
    chunks = ingest.build()
    get_retriever.cache_clear()

    quality_points = 0
    if settings.data_quality_json.exists():
        data = json.loads(settings.data_quality_json.read_text(encoding="utf-8"))
        quality_points = len(data.get("problemas", []))

    print(f"Banco gerado em: {settings.catalog_db}")
    print("Contagens:")
    for name, count in report["contagens"].items():
        print(f"  {name}: {count}")
    print(f"Trechos de política: {len(chunks)}")
    print(f"Pontos de qualidade de dados: {quality_points}")


if __name__ == "__main__":
    main()
