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
    monkeypatch.delenv("OPENAI_TIMEOUT_SECONDS", raising=False)

    settings = get_openai_settings()

    assert settings.timeout_seconds == 300.0


def test_generation_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("SCRIPT_AI_MAX_CONCURRENCY", "7")

    settings = get_script_generation_settings()

    assert settings.max_concurrency == 7


def test_openai_timeout_reads_environment(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
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
    monkeypatch.setenv("OPENAI_TIMEOUT_SECONDS", value)

    with pytest.raises(
        ValueError,
        match="must be a positive number",
    ):
        get_openai_settings()


def test_production_profile_uses_task_specific_defaults(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    for name in (
        "OPENAI_COMMON_MODEL",
        "OPENAI_COMMON_REASONING_EFFORT",
        "OPENAI_PERSONAL_MODEL",
        "OPENAI_PERSONAL_REASONING_EFFORT",
    ):
        monkeypatch.delenv(name, raising=False)

    settings = get_openai_settings()

    assert settings.common.model == "gpt-5.6-terra"
    assert settings.common.reasoning_effort == "medium"
    assert settings.personal.model == "gpt-5.6-luna"
    assert settings.personal.reasoning_effort == "none"


def test_check_profile_uses_lightweight_model_for_all_tasks(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.delenv("OPENAI_CHECK_MODEL", raising=False)
    monkeypatch.delenv(
        "OPENAI_CHECK_REASONING_EFFORT",
        raising=False,
    )

    settings = get_openai_settings(profile="check")

    assert settings.common.model == "gpt-5.6-luna"
    assert settings.common.reasoning_effort == "none"
    assert settings.personal == settings.common


def test_model_settings_read_environment(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("OPENAI_COMMON_MODEL", "common-test")
    monkeypatch.setenv(
        "OPENAI_COMMON_REASONING_EFFORT",
        "high",
    )
    monkeypatch.setenv("OPENAI_PERSONAL_MODEL", "personal-test")
    monkeypatch.setenv(
        "OPENAI_PERSONAL_REASONING_EFFORT",
        "low",
    )

    settings = get_openai_settings()

    assert settings.common.model == "common-test"
    assert settings.common.reasoning_effort == "high"
    assert settings.personal.model == "personal-test"
    assert settings.personal.reasoning_effort == "low"


def test_openai_settings_reject_invalid_reasoning_effort(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv(
        "OPENAI_COMMON_REASONING_EFFORT",
        "invalid",
    )

    with pytest.raises(ValueError, match="must be one of"):
        get_openai_settings()


def test_openai_settings_reject_invalid_profile(
    monkeypatch,
) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")

    with pytest.raises(ValueError, match="profile"):
        get_openai_settings(profile="invalid")
