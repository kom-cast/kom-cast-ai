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


def get_openai_settings() -> OpenAiSettings:
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL")

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
    )
