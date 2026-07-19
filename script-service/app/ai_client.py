from abc import ABC, abstractmethod

from openai import AsyncOpenAI

from app.config import get_openai_settings


SCRIPT_INSTRUCTIONS = """
당신은 개인 투자자를 위한 금융 뉴스 오디오 브리핑 작가입니다.

입력으로 한 종목에 대한 여러 뉴스 요약이 주어집니다.
뉴스의 핵심 내용을 종합하여 자연스럽게 들을 수 있는
한국어 오디오 스크립트를 작성하세요.

작성 규칙:
1. 뉴스에 없는 사실을 만들지 마세요.
2. 투자 추천이나 매수·매도 지시를 하지 마세요.
3. 같은 내용을 반복하지 마세요.
4. 기사별 나열이 아니라 하나의 흐름으로 통합하세요.
5. 종목에 긍정적인 요인과 위험 요인을 균형 있게 설명하세요.
6. 전문 용어는 일반 투자자가 이해하기 쉽게 설명하세요.
7. 60초 안팎으로 들을 수 있는 분량으로 작성하세요.
8. 제목, 번호, 마크다운 없이 말하듯 작성하세요.
""".strip()


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
