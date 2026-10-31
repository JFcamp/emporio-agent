from datetime import date, datetime

import pytest
from pydantic import ValidationError

from emporio.config import STORE_TZ, Settings


def test_defaults():
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "groq"
    assert settings.groq_api_key is None
    assert settings.groq_model == "openai/gpt-oss-120b"
    assert settings.ollama_model == "qwen3:8b"
    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.llm_temperature == 0.2
    assert settings.reference_date is None
    assert settings.max_history_messages == 20


def test_reference_date_fixed():
    settings = Settings(_env_file=None, reference_date="2026-02-20")
    assert settings.today() == date(2026, 2, 20)


def test_reference_date_empty_is_none_and_today_matches_store_tz():
    settings = Settings(_env_file=None, reference_date="")
    assert settings.reference_date is None
    assert settings.today() == datetime.now(STORE_TZ).date()


def test_env_overrides_defaults(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    settings = Settings(_env_file=None)
    assert settings.llm_provider == "ollama"


def test_invalid_provider_raises():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="invalid")


def test_derived_paths_live_under_data_dirs():
    settings = Settings(_env_file=None)
    assert settings.catalog_db.parent == settings.processed_dir
    assert settings.policies_json.parent == settings.processed_dir
    assert settings.data_quality_json.parent == settings.processed_dir
    assert settings.checkpoints_db.parent == settings.runtime_dir
    assert settings.handoffs_file.parent == settings.runtime_dir
