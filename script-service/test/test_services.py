from dataclasses import dataclass
from datetime import datetime
from unittest.mock import AsyncMock, Mock

import pytest

from app.ai_client import AiClient
from app.models import StockScript
from app.repositories import NewsRepository, ScriptRepository
from app.services import ScriptService


@dataclass
class FakeNewsSummary:
    title: str
    summary_content: str


class TestScriptService:
    @pytest.mark.asyncio
    async def test_generate_scripts_generates_script_for_each_stock(
        self,
    ) -> None:
        # given
        news_repository = Mock(spec=NewsRepository)

        stock_1_news = [
            FakeNewsSummary(
                title="삼성전자 반도체 투자 확대",
                summary_content="삼성전자가 반도체 설비 투자를 확대했다.",
            ),
        ]

        stock_2_news = [
            FakeNewsSummary(
                title="SK하이닉스 신규 제품 발표",
                summary_content="SK하이닉스가 신규 메모리 제품을 발표했다."
            ),
        ]

        news_repository.find_news_summaries.side_effect = [
            stock_1_news,
            stock_2_news,
        ]

        ai_client = Mock(spec=AiClient)
        ai_client.generate_script = AsyncMock(
            side_effect=[
                "삼성전자 스크립트",
                "SK하이닉스 스크립트",
            ]
        )

        script_repository = Mock(spec=ScriptRepository)
        service = ScriptService(
            news_repository=news_repository,
            script_repository=script_repository,
            ai_client=ai_client,
        )

        start_at = datetime(2026, 7, 18, 0, 0)
        end_at = datetime(2026, 7, 19, 0, 0)

        # when
        result = await service.generate_scripts(
            stock_ids=[1, 2],
            start_at=start_at,
            end_at=end_at,
        )

        # then
        assert result == {
            1: "삼성전자 스크립트",
            2: "SK하이닉스 스크립트",
        }

        assert (news_repository.find_news_summaries.call_count== 2)

        news_repository.find_news_summaries.assert_any_call(
            stock_id=1,
            start_at=start_at,
            end_at=end_at,
        )

        news_repository.find_news_summaries.assert_any_call(
            stock_id=2,
            start_at=start_at,
            end_at=end_at,
        )

        assert ai_client.generate_script.await_count == 2

    @pytest.mark.asyncio
    async def test_generate_scripts_passes_combined_news_to_ai(
        self,
    ) -> None:
        # given
        news_repository = Mock(spec=NewsRepository)
        news_repository.find_news_summaries.return_value = [
            FakeNewsSummary(
                title="첫 번째 뉴스",
                summary_content="첫 번째 뉴스 요약",
            ),
            FakeNewsSummary(
                title="두 번째 뉴스",
                summary_content="두 번째 뉴스 요약",
            ),
        ]

        ai_client = Mock(spec=AiClient)
        ai_client.generate_script = AsyncMock(
            return_value="생성된 스크립트"
        )

        script_repository = Mock(spec=ScriptRepository)
        service = ScriptService(
            news_repository=news_repository,
            script_repository=script_repository,
            ai_client=ai_client,
        )

        start_at = datetime(2026, 7, 18, 0, 0)
        end_at = datetime(2026, 7, 19, 0, 0)

        # when
        result = await service.generate_scripts(
            stock_ids=[10],
            start_at=start_at,
            end_at=end_at,
        )

        # then
        assert result == {
            10: "생성된 스크립트",
        }

        ai_client.generate_script.assert_awaited_once_with(
            (
                "종목 ID: 10\n\n"
                "다음은 해당 종목과 관련된 뉴스 요약입니다.\n\n"
                "[뉴스 1]\n"
                "제목: 첫 번째 뉴스\n"
                "요약: 첫 번째 뉴스 요약\n\n"
                "[뉴스 2]\n"
                "제목: 두 번째 뉴스\n"
                "요약: 두 번째 뉴스 요약"
            )
        )

    @pytest.mark.asyncio
    async def test_generate_scripts_does_not_call_ai_when_news_is_empty(
        self,
    ) -> None:
        # given
        news_repository = Mock(spec=NewsRepository)
        news_repository.find_news_summaries.return_value = []

        ai_client = Mock(spec=AiClient)
        ai_client.generate_script = AsyncMock()

        script_repository = Mock(spec=ScriptRepository)
        service = ScriptService(
            news_repository=news_repository,
            script_repository=script_repository,
            ai_client=ai_client,
        )

        start_at = datetime(2026, 7, 18, 0, 0)
        end_at = datetime(2026, 7, 19, 0, 0)

        # when
        result = await service.generate_scripts(
            stock_ids=[1],
            start_at=start_at,
            end_at=end_at,
        )

        # then
        assert result == {
            1: "",
        }

        ai_client.generate_script.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_generate_scripts_removes_duplicate_stock_ids(
        self,
    ) -> None:
        # given
        news_repository = Mock(spec=NewsRepository)
        news_repository.find_news_summaries.return_value = [
            FakeNewsSummary(
                title="뉴스 제목",
                summary_content="뉴스 요약",
            )
        ]

        ai_client = Mock(spec=AiClient)
        ai_client.generate_script = AsyncMock(
            return_value="생성된 스크립트"
        )

        script_repository = Mock(spec=ScriptRepository)
        service = ScriptService(
            news_repository=news_repository,
            script_repository=script_repository,
            ai_client=ai_client,
        )

        start_at = datetime(2026, 7, 18, 0, 0)
        end_at = datetime(2026, 7, 19, 0, 0)

        # when
        result = await service.generate_scripts(
            stock_ids=[1, 1, 1],
            start_at=start_at,
            end_at=end_at,
        )

        # then
        assert result == {
            1: "생성된 스크립트",
        }

        news_repository.find_news_summaries.assert_called_once()
        ai_client.generate_script.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_generate_scripts_returns_empty_dict_when_stock_ids_empty(
        self,
    ) -> None:
        # given
        news_repository = Mock(spec=NewsRepository)

        ai_client = Mock(spec=AiClient)
        ai_client.generate_script = AsyncMock()

        script_repository = Mock(spec=ScriptRepository)
        service = ScriptService(
            news_repository=news_repository,
            script_repository=script_repository,
            ai_client=ai_client,
        )

        start_at = datetime(2026, 7, 18, 0, 0)
        end_at = datetime(2026, 7, 19, 0, 0)

        # when
        result = await service.generate_scripts(
            stock_ids=[],
            start_at=start_at,
            end_at=end_at,
        )

        # then
        assert result == {}

        news_repository.find_news_summaries.assert_not_called()
        ai_client.generate_script.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_generate_scripts_raises_error_when_period_is_invalid(
        self,
    ) -> None:
        # given
        news_repository = Mock(spec=NewsRepository)

        ai_client = Mock(spec=AiClient)
        ai_client.generate_script = AsyncMock()

        script_repository = Mock(spec=ScriptRepository)
        service = ScriptService(
            news_repository=news_repository,
            script_repository=script_repository,
            ai_client=ai_client,
        )

        same_time = datetime(2026, 7, 19, 0, 0)

        # when & then
        with pytest.raises(
            ValueError,
            match="start_at must be earlier than end_at",
        ):
            await service.generate_scripts(
                stock_ids=[1],
                start_at=same_time,
                end_at=same_time,
            )

        news_repository.find_news_summaries.assert_not_called()
        ai_client.generate_script.assert_not_awaited()

    def test_constructor_raises_error_when_max_concurrency_is_zero(
        self,
    ) -> None:
        # given
        news_repository = Mock(spec=NewsRepository)
        ai_client = Mock(spec=AiClient)
        script_repository = Mock(spec=ScriptRepository)

        # when & then
        with pytest.raises(
            ValueError,
            match="max_concurrency must be greater than 0",
        ):
            ScriptService(
                news_repository=news_repository,
                script_repository=script_repository,
                ai_client=ai_client,
                max_concurrency=0,
            )

    @pytest.mark.asyncio
    async def test_generate_scripts_saves_generated_script(
        self,
    ) -> None:
        # given
        news_repository = Mock(spec=NewsRepository)
        script_repository = Mock(spec=ScriptRepository)
        ai_client = Mock(spec=AiClient)

        news_repository.find_news_summaries.return_value = [
            FakeNewsSummary(
                title="삼성전자 반도체 투자 확대",
                summary_content=(
                    "삼성전자가 반도체 설비 투자를 확대했다."
                ),
            )
        ]

        ai_client.generate_script = AsyncMock(
            return_value="생성된 삼성전자 스크립트"
        )

        service = ScriptService(
            news_repository=news_repository,
            script_repository=script_repository,
            ai_client=ai_client,
        )

        start_at = datetime(2026, 7, 18, 0, 0)
        end_at = datetime(2026, 7, 19, 0, 0)

        # when
        result = await service.generate_scripts(
            stock_ids=[1],
            start_at=start_at,
            end_at=end_at,
        )

        # then
        assert result == {
            1: "생성된 삼성전자 스크립트",
        }

        script_repository.save.assert_called_once()

        saved_script = (
            script_repository.save.call_args.args[0]
        )

        assert isinstance(saved_script, StockScript)
        assert saved_script.stock_id == 1
        assert saved_script.start_at == start_at
        assert saved_script.end_at == end_at
        assert (
            saved_script.script_content
            == "생성된 삼성전자 스크립트"
        )

    @pytest.mark.asyncio
    async def test_generate_scripts_does_not_save_when_news_is_empty(
        self,
    ) -> None:
        # given
        news_repository = Mock(spec=NewsRepository)
        script_repository = Mock(spec=ScriptRepository)
        ai_client = Mock(spec=AiClient)

        news_repository.find_news_summaries.return_value = []
        ai_client.generate_script = AsyncMock()

        service = ScriptService(
            news_repository=news_repository,
            script_repository=script_repository,
            ai_client=ai_client,
        )

        start_at = datetime(2026, 7, 18, 0, 0)
        end_at = datetime(2026, 7, 19, 0, 0)

        # when
        result = await service.generate_scripts(
            stock_ids=[1],
            start_at=start_at,
            end_at=end_at,
        )

        # then
        assert result == {
            1: "",
        }

        ai_client.generate_script.assert_not_awaited()
        script_repository.save.assert_not_called()
