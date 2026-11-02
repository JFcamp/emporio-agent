import os
import shutil
import time

from emporio import bootstrap
from emporio.config import get_settings


def test_ensure_data_creates_artifacts():
    settings = get_settings()
    settings.catalog_db.unlink(missing_ok=True)
    settings.policies_json.unlink(missing_ok=True)

    bootstrap.ensure_data()

    assert settings.catalog_db.exists()
    assert settings.policies_json.exists()


def test_ensure_data_skips_when_up_to_date():
    settings = get_settings()
    bootstrap.ensure_data(force=True)
    db_mtime = settings.catalog_db.stat().st_mtime
    policies_mtime = settings.policies_json.stat().st_mtime

    time.sleep(0.01)
    bootstrap.ensure_data()  # nada mudou: não deve reconstruir

    assert settings.catalog_db.stat().st_mtime == db_mtime
    assert settings.policies_json.stat().st_mtime == policies_mtime


def test_ensure_data_rebuilds_when_raw_newer(tmp_path):
    settings = get_settings()
    bootstrap.ensure_data(force=True)
    db_mtime = settings.catalog_db.stat().st_mtime

    # Trabalha sobre uma CÓPIA de data/raw; o raw real nunca é tocado.
    raw_copy = tmp_path / "raw"
    shutil.copytree(settings.raw_dir, raw_copy)
    original_raw = settings.raw_dir
    settings.raw_dir = raw_copy
    try:
        future = time.time() + 10
        os.utime(raw_copy / "products.csv", (future, future))
        bootstrap.ensure_data()
        assert settings.catalog_db.stat().st_mtime > db_mtime
    finally:
        settings.raw_dir = original_raw
