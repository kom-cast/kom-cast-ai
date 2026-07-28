from datetime import date, datetime, timezone
from unittest.mock import AsyncMock, Mock

import pytest
from openai import OpenAIError

from script_app.ai_client import AiClient
from script_app.models import (
    NewsArticle,
    Section,
    SectionTargetType,
    SectionType,
)
from script_app.repositories import (
    NewsRepository,
    SectionRepository,
    TargetRepository,
)
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
    target_repository = Mock(spec=TargetRepository)
    target_repository.find_stocks.return_value = {}
    target_repository.find_industries.return_value = {}
    section_repository = Mock(spec=SectionRepository)
    ai_client = Mock(spec=AiClient)
    service = CommonSectionService(
        news_repository=news_repository,
        target_repository=target_repository,
        section_repository=section_repository,
        ai_client=ai_client,
    )
    return (
        service,
        news_repository,
        target_repository,
        section_repository,
        ai_client,
    )


def test_common_source_prefers_news_summary() -> None:
    article = news("삼성전자 투자 뉴스")
    article.summary = "AI 생성용 뉴스 요약"

    source = CommonSectionService._build_source(
        section_type=SectionType.STOCK,
        target_code="005930",
        target_name="삼성전자",
        news_articles=[article],
    )

    assert "요약: AI 생성용 뉴스 요약" in source
    assert "삼성전자 투자 뉴스 요약" not in source


@pytest.mark.asyncio
async def test_reuses_existing_sections_without_ai_call() -> None:
    (
        service,
        news_repository,
        target_repository,
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
        target_repository,
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
    target_repository.find_stocks.return_value = {
        "005930": Mock(corp_name="삼성전자")
    }
    target_repository.find_industries.return_value = {
        "SEMI": Mock(industry_name="반도체")
    }
    ai_client.generate_common_section = AsyncMock(
        side_effect=[
            ai_response("삼성전자 소식입니다."),
            ai_response("반도체 업종 소식입니다."),
        ]
    )
    (
        section_repository
        .save_common_section_with_lines_or_get
        .side_effect
    ) = (
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
    sources = [
        call.args[0]
        for call in ai_client.generate_common_section.await_args_list
    ]
    assert "대상 이름: 삼성전자" in sources[0]
    assert "대상 이름: 반도체" in sources[1]
    assert (
        section_repository
        .save_common_section_with_lines_or_get
        .call_count
        == 2
    )
    saved_lines = (
        section_repository
        .save_common_section_with_lines_or_get
        .call_args_list[0]
        .args[1]
    )
    assert saved_lines[0].talker == "코스"


@pytest.mark.asyncio
async def test_passes_only_three_selected_news_to_ai() -> None:
    (
        service,
        news_repository,
        target_repository,
        section_repository,
        ai_client,
    ) = create_service()
    section_repository.find_stock_sections.return_value = {}
    section_repository.find_industry_sections.return_value = {}
    articles = [
        news(f"삼성전자 주요 뉴스 {index}")
        for index in range(1, 101)
    ]

    for index, article in enumerate(articles, start=1):
        article.summary = (
            f"고유사건{index}의 독립변화{index}와 "
            "시장 영향을 다룬 요약입니다."
        )

    news_repository.find_by_stock_codes.return_value = {
        "005930": articles
    }
    news_repository.find_by_industry_codes.return_value = {}
    target_repository.find_stocks.return_value = {
        "005930": Mock(corp_name="삼성전자")
    }
    ai_client.generate_common_section = AsyncMock(
        return_value=ai_response("선별된 뉴스입니다.")
    )
    (
        section_repository
        .save_common_section_with_lines_or_get
        .side_effect
    ) = lambda section, lines: section

    await service.prepare_sections(
        stock_codes=["005930"],
        industry_codes=[],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    source = (
        ai_client.generate_common_section.await_args.args[0]
    )
    assert source.count("\n뉴스 ") == 3
    assert "뉴스 4" not in source


@pytest.mark.asyncio
async def test_reports_targets_without_news() -> None:
    (
        service,
        news_repository,
        target_repository,
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
        target_repository,
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
            OpenAIError("AI error"),
            ai_response("성공한 소식입니다."),
        ]
    )
    (
        section_repository
        .save_common_section_with_lines_or_get
        .side_effect
    ) = (
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
    assert (
        section_repository
        .save_common_section_with_lines_or_get
        .call_count
        == 1
    )


@pytest.mark.asyncio
async def test_unexpected_common_generation_error_is_not_hidden() -> None:
    (
        service,
        news_repository,
        target_repository,
        section_repository,
        ai_client,
    ) = create_service()
    section_repository.find_stock_sections.return_value = {}
    section_repository.find_industry_sections.return_value = {}
    news_repository.find_by_stock_codes.return_value = {
        "005930": [news("삼성전자 뉴스")]
    }
    news_repository.find_by_industry_codes.return_value = {}
    ai_client.generate_common_section = AsyncMock(
        side_effect=RuntimeError("programming error")
    )

    with pytest.raises(
        RuntimeError,
        match="programming error",
    ):
        await service.prepare_sections(
            stock_codes=["005930"],
            industry_codes=[],
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )


def test_common_section_service_requires_positive_concurrency() -> None:
    with pytest.raises(
        ValueError,
        match="max_concurrency must be greater than 0",
    ):
        CommonSectionService(
            news_repository=Mock(spec=NewsRepository),
            target_repository=Mock(spec=TargetRepository),
            section_repository=Mock(spec=SectionRepository),
            ai_client=Mock(spec=AiClient),
            max_concurrency=0,
        )
