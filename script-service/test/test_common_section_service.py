from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest

from script_app.ai_client import AiClient
from script_app.models import (
    NewsArticle,
    Section,
    SectionTargetType,
    SectionType,
)
from script_app.repositories import NewsRepository, SectionRepository
from script_app.schemas import CommonSectionAiResponse
from script_app.services import CommonSectionService


PERIOD_START = datetime(2026, 7, 22, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 23, tzinfo=timezone.utc)


def news(title: str) -> NewsArticle:
    return NewsArticle(
        source="테스트 언론사",
        news_date=date(2026, 7, 22),
        published_at=PERIOD_START,
        title=title,
        body=f"{title} 요약",
    )


def ai_response(content: str) -> CommonSectionAiResponse:
    return CommonSectionAiResponse(
        lines=[
            {
                "talker": "코스",
                "content": content,
            }
        ]
    )


def existing_stock_section(stock_code: str) -> Section:
    return Section(
        section_type=SectionType.STOCK,
        target_type=SectionTargetType.STOCK,
        stock_code=stock_code,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )


def create_service():
    news_repository = Mock(spec=NewsRepository)
    section_repository = Mock(spec=SectionRepository)
    ai_client = Mock(spec=AiClient)
    service = CommonSectionService(
        news_repository=news_repository,
        section_repository=section_repository,
        ai_client=ai_client,
    )
    return (
        service,
        news_repository,
        section_repository,
        ai_client,
    )


@pytest.mark.asyncio
async def test_reuses_existing_sections_without_ai_call() -> None:
    (
        service,
        news_repository,
        section_repository,
        ai_client,
    ) = create_service()
    reusable = existing_stock_section("005930")
    section_repository.find_stock_sections.return_value = {
        "005930": reusable
    }
    section_repository.find_industry_sections.return_value = {}
    news_repository.find_by_stock_codes.return_value = {}
    news_repository.find_by_industry_codes.return_value = {}
    ai_client.generate_common_section = AsyncMock()

    result = await service.prepare_sections(
        stock_codes=["005930"],
        industry_codes=[],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result.stock_sections == {"005930": reusable}
    news_repository.find_by_stock_codes.assert_called_once_with(
        [],
        start_at=PERIOD_START,
        end_at=PERIOD_END,
    )
    ai_client.generate_common_section.assert_not_awaited()


@pytest.mark.asyncio
async def test_generates_and_saves_missing_common_sections() -> None:
    (
        service,
        news_repository,
        section_repository,
        ai_client,
    ) = create_service()
    section_repository.find_stock_sections.return_value = {}
    section_repository.find_industry_sections.return_value = {}
    news_repository.find_by_stock_codes.return_value = {
        "005930": [news("삼성전자 투자 뉴스")]
    }
    news_repository.find_by_industry_codes.return_value = {
        "SEMI": [news("반도체 업종 뉴스")]
    }
    ai_client.generate_common_section = AsyncMock(
        side_effect=[
            ai_response("삼성전자 소식입니다."),
            ai_response("반도체 업종 소식입니다."),
        ]
    )
    section_repository.save_with_lines.side_effect = (
        lambda section, lines: section
    )

    result = await service.prepare_sections(
        stock_codes=["005930"],
        industry_codes=["SEMI"],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert set(result.stock_sections) == {"005930"}
    assert set(result.industry_sections) == {"SEMI"}
    assert ai_client.generate_common_section.await_count == 2
    assert section_repository.save_with_lines.call_count == 2
    saved_lines = (
        section_repository.save_with_lines.call_args_list[0].args[1]
    )
    assert saved_lines[0].talker == "코스"


@pytest.mark.asyncio
async def test_reports_targets_without_news() -> None:
    (
        service,
        news_repository,
        section_repository,
        ai_client,
    ) = create_service()
    section_repository.find_stock_sections.return_value = {}
    section_repository.find_industry_sections.return_value = {}
    news_repository.find_by_stock_codes.return_value = {
        "005930": []
    }
    news_repository.find_by_industry_codes.return_value = {
        "SEMI": []
    }
    ai_client.generate_common_section = AsyncMock()

    result = await service.prepare_sections(
        stock_codes=["005930"],
        industry_codes=["SEMI"],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result.no_news_stock_codes == {"005930"}
    assert result.no_news_industry_codes == {"SEMI"}
    ai_client.generate_common_section.assert_not_awaited()


@pytest.mark.asyncio
async def test_isolates_ai_failure_by_target() -> None:
    (
        service,
        news_repository,
        section_repository,
        ai_client,
    ) = create_service()
    section_repository.find_stock_sections.return_value = {}
    section_repository.find_industry_sections.return_value = {}
    news_repository.find_by_stock_codes.return_value = {
        "000660": [news("실패할 뉴스")],
        "005930": [news("성공할 뉴스")],
    }
    news_repository.find_by_industry_codes.return_value = {}
    ai_client.generate_common_section = AsyncMock(
        side_effect=[
            RuntimeError("AI error"),
            ai_response("성공한 소식입니다."),
        ]
    )
    section_repository.save_with_lines.side_effect = (
        lambda section, lines: section
    )

    result = await service.prepare_sections(
        stock_codes=["000660", "005930"],
        industry_codes=[],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result.failed_stock_codes == {"000660"}
    assert set(result.stock_sections) == {"005930"}
    assert section_repository.save_with_lines.call_count == 1


def test_common_section_service_requires_positive_concurrency() -> None:
    with pytest.raises(
        ValueError,
        match="max_concurrency must be greater than 0",
    ):
        CommonSectionService(
            news_repository=Mock(spec=NewsRepository),
            section_repository=Mock(spec=SectionRepository),
            ai_client=Mock(spec=AiClient),
            max_concurrency=0,
        )
