from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest

from script_app.ai_client import AiClient
from script_app.models import (
    Industry,
    IndustryPrice,
    MarketPrice,
    Section,
    SectionLine,
    SectionTargetType,
    SectionType,
    Stock,
)
from script_app.repositories import (
    PriceRepository,
    SectionRepository,
    TargetRepository,
)
from script_app.schemas import PersonalSectionsAiResponse
from script_app.services import PersonalSectionService


PERIOD_START = datetime(2026, 7, 22, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 23, tzinfo=timezone.utc)


def content_section(
    *,
    section_id: int,
    section_type: SectionType,
    target_code: str,
) -> Section:
    is_stock = section_type == SectionType.STOCK
    return Section(
        id=UUID(int=section_id),
        section_type=section_type,
        target_type=(
            SectionTargetType.STOCK
            if is_stock
            else SectionTargetType.INDUSTRY
        ),
        stock_code=target_code if is_stock else None,
        industry_code=None if is_stock else target_code,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )


def section_line(
    *,
    line_id: int,
    section: Section,
    talker: str,
    content: str,
) -> SectionLine:
    return SectionLine(
        id=UUID(int=line_id),
        section_id=section.id,
        line_order=line_id,
        talker=talker,
        content=content,
    )


def personal_response(
    bridge_count: int,
) -> PersonalSectionsAiResponse:
    return PersonalSectionsAiResponse(
        opening=[
            {
                "talker": "코스",
                "content": "맞춤형 브리핑을 시작하겠습니다.",
            }
        ],
        bridges=[
            [
                {
                    "talker": "코스",
                    "content": f"다음 소식 {index}입니다.",
                }
            ]
            for index in range(bridge_count)
        ],
        closing=[
            {
                "talker": "코미",
                "content": "오늘 브리핑을 마무리하겠습니다.",
            }
        ],
    )


def create_service():
    section_repository = Mock(spec=SectionRepository)
    price_repository = Mock(spec=PriceRepository)
    price_repository.find_latest_stock_prices.return_value = {}
    price_repository.find_latest_industry_prices.return_value = {}
    target_repository = Mock(spec=TargetRepository)
    target_repository.find_stocks.return_value = {}
    target_repository.find_industries.return_value = {}
    ai_client = Mock(spec=AiClient)
    ai_client.generate_personal_sections = AsyncMock()
    service = PersonalSectionService(
        section_repository=section_repository,
        price_repository=price_repository,
        target_repository=target_repository,
        ai_client=ai_client,
    )
    return service, section_repository, ai_client


@pytest.mark.asyncio
async def test_generates_personal_sections_in_one_ai_call() -> None:
    service, section_repository, ai_client = create_service()
    industry = content_section(
        section_id=1,
        section_type=SectionType.INDUSTRY,
        target_code="SEMI",
    )
    stock = content_section(
        section_id=2,
        section_type=SectionType.STOCK,
        target_code="005930",
    )
    section_repository.find_lines_by_section_ids.return_value = {
        industry.id: [
            section_line(
                line_id=1,
                section=industry,
                talker="코스",
                content="반도체 업종 소식입니다.",
            )
        ],
        stock.id: [
            section_line(
                line_id=2,
                section=stock,
                talker="코미",
                content="삼성전자 소식입니다.",
            )
        ],
    }
    ai_client.generate_personal_sections.return_value = (
        personal_response(bridge_count=1)
    )
    section_repository.save_with_lines.side_effect = (
        lambda section, lines: section
    )

    result = await service.generate_sections(
        [industry, stock],
        stock_codes=["005930"],
        industry_codes=["SEMI"],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    ai_client.generate_personal_sections.assert_awaited_once()
    source = ai_client.generate_personal_sections.await_args.args[0]
    assert (
        f"브리핑 기준 시각: {PERIOD_END.isoformat()}"
        in source
    )
    assert len(result.bridges) == 1
    assert section_repository.save_with_lines.call_count == 3
    assert [
        section.section_type
        for section in result.assemble([industry, stock])
    ] == [
        SectionType.OPENING,
        SectionType.INDUSTRY,
        SectionType.BRIDGE,
        SectionType.STOCK,
        SectionType.CLOSING,
    ]


@pytest.mark.asyncio
async def test_single_content_section_has_no_bridge() -> None:
    service, section_repository, ai_client = create_service()
    stock = content_section(
        section_id=1,
        section_type=SectionType.STOCK,
        target_code="005930",
    )
    section_repository.find_lines_by_section_ids.return_value = {
        stock.id: []
    }
    ai_client.generate_personal_sections.return_value = (
        personal_response(bridge_count=0)
    )
    section_repository.save_with_lines.side_effect = (
        lambda section, lines: section
    )

    result = await service.generate_sections(
        [stock],
        stock_codes=["005930"],
        industry_codes=[],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result.bridges == []
    assert [
        section.section_type
        for section in result.assemble([stock])
    ] == [
        SectionType.OPENING,
        SectionType.STOCK,
        SectionType.CLOSING,
    ]


@pytest.mark.asyncio
async def test_personal_section_source_contains_ordered_content() -> None:
    service, section_repository, ai_client = create_service()
    industry = content_section(
        section_id=1,
        section_type=SectionType.INDUSTRY,
        target_code="SEMI",
    )
    stock = content_section(
        section_id=2,
        section_type=SectionType.STOCK,
        target_code="005930",
    )
    section_repository.find_lines_by_section_ids.return_value = {
        industry.id: [],
        stock.id: [],
    }
    ai_client.generate_personal_sections.return_value = (
        personal_response(bridge_count=1)
    )
    section_repository.save_with_lines.side_effect = (
        lambda section, lines: section
    )

    await service.generate_sections(
        [industry, stock],
        stock_codes=["005930"],
        industry_codes=["SEMI"],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    source = (
        ai_client.generate_personal_sections.await_args.args[0]
    )
    assert source.index("대상 코드: SEMI") < source.index(
        "대상 코드: 005930"
    )
    assert (
        ai_client.generate_personal_sections.await_args.kwargs[
            "content_section_count"
        ]
        == 2
    )


@pytest.mark.asyncio
async def test_personal_section_source_contains_latest_prices() -> None:
    service, section_repository, ai_client = create_service()
    industry = content_section(
        section_id=1,
        section_type=SectionType.INDUSTRY,
        target_code="SEMI",
    )
    stock = content_section(
        section_id=2,
        section_type=SectionType.STOCK,
        target_code="005930",
    )
    section_repository.find_lines_by_section_ids.return_value = {
        industry.id: [],
        stock.id: [],
    }
    market_price = Mock(spec=MarketPrice)
    market_price.traded_at = datetime(
        2026,
        7,
        22,
        15,
        tzinfo=timezone.utc,
    )
    market_price.close_price = Decimal("270000")
    market_price.change_rate = Decimal("3.65")
    newsless_market_price = Mock(spec=MarketPrice)
    newsless_market_price.traded_at = datetime(
        2026,
        7,
        22,
        15,
        tzinfo=timezone.utc,
    )
    newsless_market_price.close_price = Decimal("210000")
    newsless_market_price.change_rate = Decimal("-0.75")
    industry_price = Mock(spec=IndustryPrice)
    industry_price.traded_at = datetime(
        2026,
        7,
        22,
        15,
        tzinfo=timezone.utc,
    )
    industry_price.index_value = Decimal("12345.67")
    industry_price.change_rate = Decimal("-1.01")
    service.price_repository.find_latest_stock_prices.return_value = {
        "005930": market_price,
        "000660": newsless_market_price,
    }
    service.price_repository.find_latest_industry_prices.return_value = {
        "SEMI": industry_price
    }
    stock_target = Mock(spec=Stock)
    stock_target.corp_name = "삼성전자"
    newsless_stock_target = Mock(spec=Stock)
    newsless_stock_target.corp_name = "SK하이닉스"
    industry_target = Mock(spec=Industry)
    industry_target.industry_name = "반도체"
    service.target_repository.find_stocks.return_value = {
        "005930": stock_target,
        "000660": newsless_stock_target,
    }
    service.target_repository.find_industries.return_value = {
        "SEMI": industry_target
    }
    ai_client.generate_personal_sections.return_value = (
        personal_response(bridge_count=1)
    )
    section_repository.save_with_lines.side_effect = (
        lambda section, lines: section
    )

    await service.generate_sections(
        [industry, stock],
        stock_codes=["005930", "000660"],
        industry_codes=["SEMI"],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    source = ai_client.generate_personal_sections.await_args.args[0]
    assert "대상: 반도체" in source
    assert "지수값: 12345.67" in source
    assert "등락: 1.01% 하락" in source
    assert "대상: 삼성전자" in source
    assert "종가: 270000원" in source
    assert "등락: 3.65% 상승" in source
    assert "대상: SK하이닉스" in source
    assert "종가: 210000원" in source
    assert "등락: 0.75% 하락" in source
    service.price_repository.find_latest_stock_prices.assert_called_once_with(
        ["005930", "000660"],
        as_of=PERIOD_END,
    )
    service.price_repository.find_latest_industry_prices.assert_called_once_with(
        ["SEMI"],
        as_of=PERIOD_END,
    )


@pytest.mark.asyncio
async def test_rejects_empty_content_sections() -> None:
    service, section_repository, ai_client = create_service()

    with pytest.raises(
        ValueError,
        match="content_sections must not be empty",
    ):
        await service.generate_sections(
            [],
            stock_codes=[],
            industry_codes=[],
            period_start=PERIOD_START,
            period_end=PERIOD_END,
        )

    section_repository.find_lines_by_section_ids.assert_not_called()
    ai_client.generate_personal_sections.assert_not_awaited()
