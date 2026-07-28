from abc import ABC, abstractmethod

from openai import AsyncOpenAI, LengthFinishReasonError
from pathlib import Path
from pydantic import ValidationError

from script_app.config import get_openai_settings
from script_app.schemas import (
    CommonSectionAiResponse,
    PersonalSectionsAiResponse,
)


PROMPT_DIR = Path(__file__).resolve().parent / "prompts"
COMMON_SECTION_PROMPT_PATH = (
    PROMPT_DIR / "common_section_prompt.txt"
)
PERSONAL_SECTIONS_PROMPT_PATH = (
    PROMPT_DIR / "personal_sections_prompt.txt"
)


def _load_prompt(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise RuntimeError(
            f"프롬프트 파일을 찾을 수 없습니다: {path}"
        ) from error


def load_common_section_prompt() -> str:
    return _load_prompt(COMMON_SECTION_PROMPT_PATH)


def load_personal_sections_prompt() -> str:
    return _load_prompt(PERSONAL_SECTIONS_PROMPT_PATH)


class AiResponseInvalidError(ValueError):
    pass


class AiClient(ABC):
    @abstractmethod
    async def generate_common_section(
        self,
        source: str,
    ) -> CommonSectionAiResponse:
        raise NotImplementedError

    @abstractmethod
    async def generate_personal_sections(
        self,
        source: str,
        content_section_count: int,
    ) -> PersonalSectionsAiResponse:
        raise NotImplementedError


class OpenAiClient(AiClient):
    def __init__(
        self,
        client: AsyncOpenAI,
        common_model: str,
        common_reasoning_effort: str,
        personal_model: str,
        personal_reasoning_effort: str,
    ) -> None:
        self.client = client
        self.common_model = common_model
        self.common_reasoning_effort = common_reasoning_effort
        self.personal_model = personal_model
        self.personal_reasoning_effort = (
            personal_reasoning_effort
        )

    async def generate_common_section(
        self,
        source: str,
    ) -> CommonSectionAiResponse:
        try:
            response = await self.client.responses.parse(
                model=self.common_model,
                reasoning={
                    "effort": self.common_reasoning_effort,
                },
                instructions=load_common_section_prompt(),
                input=source,
                text_format=CommonSectionAiResponse,
            )
        except (
            ValidationError,
            LengthFinishReasonError,
        ) as error:
            raise AiResponseInvalidError(
                "공통 섹션 응답 형식이 올바르지 않습니다."
            ) from error

        if response.output_parsed is None:
            raise AiResponseInvalidError(
                "공통 섹션 응답을 파싱할 수 없습니다."
            )

        return response.output_parsed

    async def generate_personal_sections(
        self,
        source: str,
        content_section_count: int,
    ) -> PersonalSectionsAiResponse:
        try:
            response = await self.client.responses.parse(
                model=self.personal_model,
                reasoning={
                    "effort": self.personal_reasoning_effort,
                },
                instructions=load_personal_sections_prompt(),
                input=source,
                text_format=PersonalSectionsAiResponse,
            )
        except (
            ValidationError,
            LengthFinishReasonError,
        ) as error:
            raise AiResponseInvalidError(
                "사용자 섹션 응답 형식이 올바르지 않습니다."
            ) from error

        if response.output_parsed is None:
            raise AiResponseInvalidError(
                "사용자 섹션 응답을 파싱할 수 없습니다."
            )

        try:
            return response.output_parsed.validate_bridge_count(
                content_section_count
            )
        except ValueError as error:
            raise AiResponseInvalidError(str(error)) from error


def create_openai_client(
    profile: str = "production",
) -> OpenAiClient:
    settings = get_openai_settings(profile=profile)

    async_client = AsyncOpenAI(
        api_key=settings.api_key,
        timeout=settings.timeout_seconds,
    )

    return OpenAiClient(
        client=async_client,
        common_model=settings.common.model,
        common_reasoning_effort=(
            settings.common.reasoning_effort
        ),
        personal_model=settings.personal.model,
        personal_reasoning_effort=(
            settings.personal.reasoning_effort
        ),
    )
