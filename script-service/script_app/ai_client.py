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
PROMPT_PATH = PROMPT_DIR / "script_prompt.txt"
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


def load_prompt() -> str:
    return _load_prompt(PROMPT_PATH)


def load_common_section_prompt() -> str:
    return _load_prompt(COMMON_SECTION_PROMPT_PATH)


def load_personal_sections_prompt() -> str:
    return _load_prompt(PERSONAL_SECTIONS_PROMPT_PATH)


class AiResponseInvalidError(ValueError):
    pass


class AiClient(ABC):
    @abstractmethod
    async def generate_script(self, source: str) -> str:
        """
        뉴스 요약문을 전달받아 오디오 브리핑 스크립트를 생성한다.
        """
        raise NotImplementedError

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
        model: str,
    ) -> None:
        self.client = client
        self.model = model

    async def generate_script(self, source: str) -> str:
        response = await self.client.responses.create(
            model=self.model,
            instructions=load_prompt(),
            input=source,
        )

        return response.output_text

    async def generate_common_section(
        self,
        source: str,
    ) -> CommonSectionAiResponse:
        try:
            response = await self.client.responses.parse(
                model=self.model,
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
                model=self.model,
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


def create_openai_client() -> OpenAiClient:
    settings = get_openai_settings()

    async_client = AsyncOpenAI(
        api_key=settings.api_key,
        timeout=settings.timeout_seconds,
    )

    return OpenAiClient(
        client=async_client,
        model=settings.model,
    )
