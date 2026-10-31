from datetime import date, datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal
from zoneinfo import ZoneInfo

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
STORE_TZ = ZoneInfo("America/Campo_Grande")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ROOT_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_provider: Literal["groq", "ollama"] = "groq"
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    ollama_model: str = "qwen3:8b"
    ollama_base_url: str = "http://localhost:11434"
    llm_temperature: float = 0.2
    reference_date: date | None = None
    max_history_messages: int = 20

    raw_dir: Path = ROOT_DIR / "data" / "raw"
    processed_dir: Path = ROOT_DIR / "data" / "processed"
    runtime_dir: Path = ROOT_DIR / "data" / "runtime"

    @field_validator("reference_date", mode="before")
    @classmethod
    def _empty_string_as_none(cls, value: object) -> object:
        # Campo vazio no .env representa "sem data fixa", não erro de parsing.
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @property
    def catalog_db(self) -> Path:
        return self.processed_dir / "emporio.db"

    @property
    def policies_json(self) -> Path:
        return self.processed_dir / "policies.json"

    @property
    def data_quality_json(self) -> Path:
        return self.processed_dir / "data_quality.json"

    @property
    def checkpoints_db(self) -> Path:
        return self.runtime_dir / "conversations.db"

    @property
    def handoffs_file(self) -> Path:
        return self.runtime_dir / "handoffs.jsonl"

    def today(self) -> date:
        if self.reference_date is not None:
            return self.reference_date
        return datetime.now(STORE_TZ).date()


@lru_cache
def get_settings() -> Settings:
    return Settings()
