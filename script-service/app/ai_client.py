from abc import ABC, abstractmethod

from openai import AsyncOpenAI

from app.config import get_openai_settings


SCRIPT_INSTRUCTIONS = (
    "당신은 개인 투자자를 위한 금융 뉴스 진행자입니다. "
    "입력된 뉴스 요약을 바탕으로 자연스럽게 들을 수 있는 "
    "한국어 오디오 브리핑 스크립트를 작성하세요. "
    "각 뉴스의 핵심 내용과 해당 종목에 미칠 수 있는 영향을 "
    "이해하기 쉽게 설명하세요. "
    "입력에 없는 사실은 임의로 추가하지 마세요."
)


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
            instructions=SCRIPT_INSTRUCTIONS,
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
