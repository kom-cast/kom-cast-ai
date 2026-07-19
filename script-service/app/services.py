from datetime import datetime

from app.ai_client import AiClient
from app.models import StockNewsSummary
from app.repositories import NewsRepository


class ScriptService:
    def __init__(
        self,
        news_repository: NewsRepository,
        ai_client: AiClient,
    ):
        self.news_repository = news_repository
        self.ai_client = ai_client

    def generate_script(
        self,
        stock_id: int,
        start: datetime,
        end: datetime,
    ) -> str:
        news_summaries = self.news_repository.find_news_summaries(
            stock_id=stock_id,
            start=start,
            end=end,
        )

        if not news_summaries:
            return ""

        source = self._combine_news_summaries(news_summaries)

        return self.ai_client.generate_script(source)

    def _combine_news_summaries(
        self,
        news_summaries: list[StockNewsSummary],
    ) -> str:
        news_sections = [
            f"제목: {news.title}\n요약: {news.summary_content}"
            for news in news_summaries
        ]

        return "\n\n".join(news_sections)
    