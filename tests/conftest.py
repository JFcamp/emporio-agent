import pytest

from emporio.config import get_settings
from emporio.data import etl
from emporio.policies import ingest
from emporio.policies.retriever import get_retriever


@pytest.fixture(scope="session", autouse=True)
def built_data(tmp_path_factory):
    # Redireciona artefatos gerados para um diretório temporário da sessão,
    # preservando data/raw intacto. Futuras etapas podem gerar mais artefatos aqui.
    settings = get_settings()
    base = tmp_path_factory.mktemp("emporio_data")
    settings.processed_dir = base / "processed"
    settings.runtime_dir = base / "runtime"
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)

    report = etl.build()
    ingest.build()
    get_retriever.cache_clear()
    return report
