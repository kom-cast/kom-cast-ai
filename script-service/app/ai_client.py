from abc import ABC, abstractmethod

from openai import AsyncOpenAI
from pathlib import Path

from app.config import get_openai_settings


PROMPT_PATH = (
    Path(__file__).resolve().parent
    / "prompts"
    / "script_prompt.txt"
)


def load_prompt() -> str:
    try:
        return PROMPT_PATH.read_text(encoding="utf-8").strip()
    except FileNotFoundError as error:
        raise RuntimeError(
            f"프롬프트 파일을 찾을 수 없습니다: {PROMPT_PATH}"
        ) from error


class AiClient(ABC):
    @abstractmethod
    async def generate_script(self, source: str) -> str:
        """
        뉴스 요약문을 전달받아 오디오 브리핑 스크립트를 생성한다.
        """
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


def create_openai_client() -> OpenAiClient:
    settings = get_openai_settings()

    async_client = AsyncOpenAI(
        api_key=settings.api_key,
    )

    return OpenAiClient(
        client=async_client,
        model=settings.model,
    )
