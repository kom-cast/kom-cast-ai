import os

from dotenv import load_dotenv
from openai import OpenAI

from models import News


load_dotenv()


class OpenAiClient:
    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise RuntimeError(
                "OPENAI_API_KEY가 설정되어 있지 않습니다. "
                "프로젝트 루트의 .env 파일을 확인하세요."
            )

        self.client = OpenAI(api_key=api_key)

    def generate_summary(self, news: News) -> str:
        response = self.client.responses.create(
            model="gpt-5-mini",
            instructions=(
                "당신은 금융 뉴스를 정확하게 요약하는 편집자입니다. "
                "입력된 기사에 없는 사실을 추가하지 말고, "
                "추측을 확정된 사실처럼 표현하지 마세요."
            ),
            input=f"""
다음 뉴스의 핵심 내용을 한국어로 요약하세요.

조건:
- 2~3문장으로 작성
- 핵심 사건과 그 의미를 포함
- 투자 추천이나 매수·매도 의견은 작성하지 않음
- 뉴스에 없는 내용을 추가하지 않음
- 별도 제목 없이 요약문만 출력

뉴스 제목:
{news.title}

뉴스 내용:
{news.content}
""",
        )

        summary = response.output_text.strip()

        if not summary:
            raise RuntimeError("AI가 빈 요약을 반환했습니다.")

        return summary

    def generate_script(self, news_list: list[News]) -> str:
        summaries = "\n\n".join(
            self._format_news(index, news)
            for index, news in enumerate(news_list, start=1)
        )

        response = self.client.responses.create(
            model="gpt-5-mini",
            instructions=(
                "당신은 금융 뉴스 팟캐스트의 전문 작가입니다. "
                "제공된 뉴스 요약만 근거로 자연스러운 방송 대본을 작성하세요."
            ),
            input=f"""
다음 뉴스 요약을 바탕으로 한국어 팟캐스트 대본을 작성하세요.

조건:
- 약 2분 분량
- 진행자가 실제로 말하는 자연스러운 구어체
- 인사말, 뉴스 소개, 뉴스 간 연결, 전체 정리, 마무리 순서
- 각 뉴스 제목과 핵심 내용을 빠뜨리지 않음
- 뉴스가 서로 관련 있으면 자연스럽게 연결
- 제공되지 않은 사실을 추가하지 않음
- 투자 추천 또는 매수·매도 지시를 하지 않음
- 마크다운 제목이나 글머리표 없이 실제 대본만 출력

저장된 뉴스 요약:
{summaries}
""",
        )

        script = response.output_text.strip()

        if not script:
            raise RuntimeError("AI가 빈 스크립트를 반환했습니다.")

        return script

    @staticmethod
    def _format_news(index: int, news: News) -> str:
        if news.summary is None:
            raise ValueError(
                f"요약이 없는 뉴스가 포함되어 있습니다. news_id={news.id}"
            )

        return (
            f"[뉴스 {index}]\n"
            f"제목: {news.title}\n"
            f"뉴스 작성 시간: {news.published_at:%Y-%m-%d %H:%M}\n"
            f"요약: {news.summary.content}"
        )
