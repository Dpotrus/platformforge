from collections.abc import Iterator
from pathlib import Path
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from app.config import get_settings, Settings

TEST_DATABASE_URL = (
    "postgresql+psycopg://"
    "testuser:testpassword@127.0.0.1:5432/platformforge_test"
)

SECOND_DATABASE_URL = (
    "postgresql+psycopg://"
    "testuser:testpassword@127.0.0.1:5432/platformforge_second"
)


@pytest.fixture(autouse=True)
def clear_settings_cache() -> Iterator[None]:
    get_settings.cache_clear()

    yield

    get_settings.cache_clear()


def test_settings_uses_default_values() -> None:
    settings = Settings(
        _env_file=None,
        database_url=TEST_DATABASE_URL,
    )

    assert settings.app_name == "PlatformForge API"
    assert settings.environment == "development"


def test_settings_reads_database_url_from_environment() -> None:
    with patch.dict(
            "os.environ",
            {"DATABASE_URL": TEST_DATABASE_URL},
    ):
        settings = Settings(_env_file=None)

    assert settings.database_url == TEST_DATABASE_URL


def test_environment_variable_overrides_dotenv(
        tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        f"DATABASE_URL={SECOND_DATABASE_URL}\n",
        encoding="utf-8",
    )

    with patch.dict(
            "os.environ",
            {"DATABASE_URL": TEST_DATABASE_URL},
    ):
        settings = Settings(_env_file=env_file)

    assert settings.database_url == TEST_DATABASE_URL


def test_settings_reads_dotenv_file(
        tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        (
            f"DATABASE_URL={TEST_DATABASE_URL}\n"
            "ENVIRONMENT=testing\n"
        ),
        encoding="utf-8",
    )

    with patch.dict("os.environ", {}, clear=True):
        settings = Settings(_env_file=env_file)

    assert settings.database_url == TEST_DATABASE_URL
    assert settings.environment == "testing"


def test_settings_rejects_missing_database_url() -> None:
    with patch.dict("os.environ", {}, clear=True):
        with pytest.raises(
                ValidationError,
                match="database_url",
        ):
            Settings(_env_file=None)


@pytest.mark.parametrize(
    "invalid_url",
    [
        "",
        "sqlite:///test.db",
        "postgresql://localhost/test",
        "mysql+pymysql://localhost/test",
        "invalid-url",
    ],
)
def test_settings_rejects_invalid_database_url(
        invalid_url: str,
) -> None:
    with patch.dict(
            "os.environ",
            {"DATABASE_URL": invalid_url},
    ):
        with pytest.raises(
                ValidationError,
                match="database_url",
        ):
            Settings(_env_file=None)

def test_get_settings_returns_cached_instance() -> None:
    with patch.dict(
            "os.environ",
            {"DATABASE_URL": TEST_DATABASE_URL},
    ):
        first_settings = get_settings()
        second_settings = get_settings()

    assert first_settings is second_settings

def test_get_settings_cache_clear_reloads_environment() -> None:
    with patch.dict(
            "os.environ",
            {"DATABASE_URL": TEST_DATABASE_URL},
    ):
        first_settings = get_settings()

    get_settings.cache_clear()

    with patch.dict(
            "os.environ",
            {"DATABASE_URL": SECOND_DATABASE_URL},
    ):
        second_settings = get_settings()

    assert first_settings is not second_settings
    assert first_settings.database_url == TEST_DATABASE_URL
    assert second_settings.database_url == SECOND_DATABASE_URL