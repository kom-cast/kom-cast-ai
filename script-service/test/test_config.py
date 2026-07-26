import pytest

from script_app.config import (
    get_openai_settings,
    get_script_generation_settings,
)


def test_generation_settings_use_defaults(monkeypatch) -> None:
    monkeypatch.delenv(
        "SCRIPT_AI_MAX_CONCURRENCY",
        raising=False,
    )

    settings = get_script_generation_settings()

    assert settings.max_concurrency == 5


def test_openai_timeout_uses_default(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)

    settings = get_openai_settings()

    assert settings.timeout_seconds == 300.0


def test_generation_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("SCRIPT_AI_MAX_CONCURRENCY", "7")

    settings = get_script_generation_settings()

    assert settings.max_concurrency == 7


def test_openai_timeout_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", "45.5")

    settings = get_openai_settings()

    assert settings.timeout_seconds == 45.5


@pytest.mark.parametrize("value", ["0", "-1", "invalid"])
def test_generation_settings_reject_invalid_concurrency(
    monkeypatch,
    value: str,
) -> None:
    monkeypatch.setenv("SCRIPT_AI_MAX_CONCURRENCY", value)

    with pytest.raises(
        ValueError,
        match="must be a positive integer",
    ):
        get_script_generation_settings()


@pytest.mark.parametrize("value", ["0", "-1", "invalid"])
def test_openai_settings_reject_invalid_timeout(
    monkeypatch,
    value: str,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_MODEL", "test-model")
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", value)

    with pytest.raises(
        ValueError,
        match="must be a positive number",
    ):
        get_openai_settings()
