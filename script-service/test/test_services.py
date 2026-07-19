from datetime import datetime, timezone
from unittest.mock import Mock

from app.ai_client import AiClient
from app.models import StockNewsSummary
from app.repositories import NewsRepository
from app.services import ScriptService


class TestScriptService:
    def test_generate_script_calls_ai_with_news_summaries(self) -> None:
        # given
        start=datetime(2026, 7, 16,)
        end=datetime(2026, 7, 17,)

        first_news = StockNewsSummary(
            title="삼성전자 반도체 투자 확대",
            summary_content="삼성전자가 반도체 생산시설 투자를 확대했다.",
            stock_id=1,
            news_published_at=datetime(2026, 7, 16, 9, 0,),
        )

        second_news = StockNewsSummary(
            title="삼성전자 신제품 공개",
            summary_content="삼성전자가 새로운 모바일 제품을 공개했다.",
            stock_id=1,
            news_published_at=datetime(2026, 7, 16, 15, 0,),
        )

        news_repository = Mock(spec=NewsRepository)
        news_repository.find_news_summaries.return_value = [
            first_news,
            second_news,
        ]

        ai_client = Mock(spec=AiClient)
        ai_client.generate_script.return_value = (
            "오늘 삼성전자 관련 주요 소식을 전해드립니다."
        )

        service = ScriptService(
            news_repository=news_repository,
            ai_client=ai_client,
        )

        # when
        result = service.generate_script(
            stock_id=1,
            start=start,
            end=end,
        )

        # then
        assert result == "오늘 삼성전자 관련 주요 소식을 전해드립니다."

        news_repository.find_news_summaries.assert_called_once_with(
            stock_id=1,
            start=start,
            end=end,
        )

        ai_client.generate_script.assert_called_once_with(
            "제목: 삼성전자 반도체 투자 확대\n"
            "요약: 삼성전자가 반도체 생산시설 투자를 확대했다.\n\n"
            "제목: 삼성전자 신제품 공개\n"
            "요약: 삼성전자가 새로운 모바일 제품을 공개했다."
        )

    def test_generate_script_returns_empty_string_when_news_does_not_exist(
        self,
    ) -> None:
        # given
        start=datetime(2026, 7, 16,)
        end=datetime(2026, 7, 17,)

        news_repository = Mock(spec=NewsRepository)
        news_repository.find_news_summaries.return_value = []

        ai_client = Mock(spec=AiClient)

        service = ScriptService(
            news_repository=news_repository,
            ai_client=ai_client,
        )

        # when
        result = service.generate_script(
            stock_id=1,
            start=start,
            end=end,
        )

        # then
        assert result == ""

        news_repository.find_news_summaries.assert_called_once_with(
            stock_id=1,
            start=start,
            end=end,
        )

        ai_client.generate_script.assert_not_called()
