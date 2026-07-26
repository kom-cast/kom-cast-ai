import os
from dataclasses import dataclass
from typing import Literal, cast

from dotenv import load_dotenv


load_dotenv()


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./kom_cast.db",
)


ReasoningEffort = Literal[
    "none",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
]
VALID_REASONING_EFFORTS = {
    "none",
    "low",
    "medium",
    "high",
    "xhigh",
    "max",
}


@dataclass(frozen=True)
class ModelSettings:
    model: str
    reasoning_effort: ReasoningEffort


@dataclass(frozen=True)
class OpenAiSettings:
    api_key: str
    timeout_seconds: float
    common: ModelSettings
    personal: ModelSettings


@dataclass(frozen=True)
class ScriptGenerationSettings:
    max_concurrency: int


def get_openai_settings(
    profile: str = "production",
) -> OpenAiSettings:
    api_key = os.getenv("OPENAI_API_KEY")
    timeout_seconds = _get_positive_float(
        "OPENAI_TIMEOUT_SECONDS",
        default=300.0,
    )

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required"
        )

    if profile == "production":
        common = ModelSettings(
            model=os.getenv(
                "OPENAI_COMMON_MODEL",
                "gpt-5.6-terra",
            ),
            reasoning_effort=_get_reasoning_effort(
                "OPENAI_COMMON_REASONING_EFFORT",
                default="medium",
            ),
        )
        personal = ModelSettings(
            model=os.getenv(
                "OPENAI_PERSONAL_MODEL",
                "gpt-5.6-luna",
            ),
            reasoning_effort=_get_reasoning_effort(
                "OPENAI_PERSONAL_REASONING_EFFORT",
                default="none",
            ),
        )
    elif profile == "check":
        check_settings = ModelSettings(
            model=os.getenv(
                "OPENAI_CHECK_MODEL",
                "gpt-5.6-luna",
            ),
            reasoning_effort=_get_reasoning_effort(
                "OPENAI_CHECK_REASONING_EFFORT",
                default="none",
            ),
        )
        common = check_settings
        personal = check_settings
    else:
        raise ValueError(
            "profile must be 'production' or 'check'"
        )

    return OpenAiSettings(
        api_key=api_key,
        timeout_seconds=timeout_seconds,
        common=common,
        personal=personal,
    )


def get_script_generation_settings() -> ScriptGenerationSettings:
    return ScriptGenerationSettings(
        max_concurrency=_get_positive_int(
            "SCRIPT_AI_MAX_CONCURRENCY",
            default=5,
        )
    )


def _get_positive_float(
    name: str,
    default: float,
) -> float:
    raw_value = os.getenv(name)

    try:
        value = (
            float(raw_value)
            if raw_value is not None
            else default
        )
    except ValueError as error:
        raise ValueError(
            f"{name} must be a positive number"
        ) from error

    if value <= 0:
        raise ValueError(f"{name} must be a positive number")

    return value


def _get_positive_int(
    name: str,
    default: int,
) -> int:
    raw_value = os.getenv(name)

    try:
        value = (
            int(raw_value)
            if raw_value is not None
            else default
        )
    except ValueError as error:
        raise ValueError(
            f"{name} must be a positive integer"
        ) from error

    if value <= 0:
        raise ValueError(
            f"{name} must be a positive integer"
        )

    return value


def _get_reasoning_effort(
    name: str,
    default: ReasoningEffort,
) -> ReasoningEffort:
    value = os.getenv(name, default)

    if value not in VALID_REASONING_EFFORTS:
        raise ValueError(
            f"{name} must be one of "
            "none, low, medium, high, xhigh, max"
        )

    return cast(ReasoningEffort, value)
