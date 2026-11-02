"""Utilidades compartilhadas pelas interfaces (CLI e web)."""

import logging

from emporio.config import get_settings


def setup_logging() -> None:
    settings = get_settings()
    settings.runtime_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=settings.runtime_dir / "emporio.log",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    for noisy in ("httpx", "httpcore", "urllib3", "groq", "openai"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
