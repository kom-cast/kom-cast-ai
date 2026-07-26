import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "sqlite:///./kom_cast.db",
)


@dataclass(frozen=True)
class OpenAiSettings:
    api_key: str
    model: str
    timeout_seconds: float


@dataclass(frozen=True)
class ScriptGenerationSettings:
    max_concurrency: int


def get_openai_settings() -> OpenAiSettings:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")
    timeout_seconds = _get_positive_float(
        "OPENAI_TIMEOUT_SECONDS",
        default=300.0,
    )

    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required"
        )

    if not model:
        raise ValueError(
            "OPENAI_MODEL environment variable is required"
        )

    return OpenAiSettings(
        api_key=api_key,
        model=model,
        timeout_seconds=timeout_seconds,
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
