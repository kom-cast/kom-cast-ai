from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from script_app.ai_client import AiClient
from script_app.database import Base
from script_app.models import (
    Industry,
    IndustryPrice,
    MarketPrice,
    NewsArticle,
    NewsIndustryMapping,
    NewsStockMapping,
    Script,
    ScriptStatus,
    SectionType,
    Stock,
    UserIndustry,
    UserStock,
)
from script_app.repositories import (
    NewsRepository,
    PriceRepository,
    ScriptRepository,
    SectionRepository,
    TargetRepository,
    UserInterestRepository,
)
from script_app.schemas import (
    CommonSectionAiResponse,
    PersonalSectionsAiResponse,
)
from script_app.services import (
    CommonSectionService,
    PersonalSectionService,
    ScriptGenerationService,
)


USER_ID = UUID("3ad697a8-8d7d-4f80-a66f-04d994a89611")
PERIOD_START = datetime(2026, 7, 22, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 23, tzinfo=timezone.utc)


@pytest.fixture
def session() -> Session:
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    test_session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    with test_session_factory() as test_session:
        yield test_session

    Base.metadata.drop_all(bind=test_engine)


def add_generation_data(session: Session) -> None:
    industry = Industry(
        industry_code="SEMI",
        industry_name="반도체",
    )
    stock = Stock(
        stock_code="005930",
        corp_code="00126380",
        corp_name="삼성전자",
        industry_code="SEMI",
    )
    stock_news = NewsArticle(
        source="테스트 언론사",
        news_date=date(2026, 7, 22),
        published_at=PERIOD_START,
        title="삼성전자 투자 뉴스",
        body="삼성전자가 생산 시설 투자 계획을 발표했다.",
    )
    industry_news = NewsArticle(
        source="테스트 언론사",
        news_date=date(2026, 7, 22),
        published_at=PERIOD_START,
        title="반도체 업종 뉴스",
        body="반도체 업종의 설비 투자가 확대되고 있다.",
    )
    price_timestamp = datetime(
        2026,
        7,
        22,
        15,
        tzinfo=timezone.utc,
    )
    stored_at = datetime.now(timezone.utc)
    market_price = MarketPrice(
        stock_code="005930",
        traded_at=price_timestamp,
        interval="DAILY",
        open_price=Decimal("269000"),
        high_price=Decimal("273000"),
        low_price=Decimal("263000"),
        close_price=Decimal("270000"),
        volume=16011816,
        change_rate=Decimal("3.65"),
        trading_value=4308084851750,
        market_cap=1578495224160000,
        vwap=None,
        provider="KOSCOM",
        raw_external_id="market-price-1",
    )
    industry_price = IndustryPrice(
        industry_code="SEMI",
        traded_at=price_timestamp,
        index_value=Decimal("12345.67"),
        change_amount=Decimal("-123.45"),
        change_rate=Decimal("-1.01"),
        open_value=None,
        high_value=None,
        low_value=None,
        volume=987654321,
        trading_value=12345678901234,
        market_cap=None,
        market_cap_free_float=None,
        shares_outstanding=None,
        foreign_ownership_rate=None,
        short_sale_volume=None,
        short_sale_value=None,
        provider="KOSCOM",
        raw_external_id="SEMI:20260723",
        created_at=stored_at,
        updated_at=stored_at,
    )
    session.add_all(
        [
            industry,
            stock,
            stock_news,
            industry_news,
            market_price,
            industry_price,
        ]
    )
    session.flush()
    session.add_all(
        [
            UserStock(
                user_id=USER_ID,
                stock_code="005930",
                interest_type="INTEREST",
            ),
            UserIndustry(
                user_id=USER_ID,
                industry_code="SEMI",
            ),
            NewsStockMapping(
                news_id=stock_news.id,
                stock_code="005930",
            ),
            NewsIndustryMapping(
                news_id=industry_news.id,
                industry_code="SEMI",
            ),
        ]
    )
    session.commit()


def create_generation_service(
    session: Session,
) -> tuple[ScriptGenerationService, Mock]:
    ai_client = Mock(spec=AiClient)
    ai_client.generate_common_section = AsyncMock(
        side_effect=[
            CommonSectionAiResponse(
                lines=[
                    {
                        "talker": "코스",
                        "content": "반도체 업종 소식입니다.",
                    }
                ]
            ),
            CommonSectionAiResponse(
                lines=[
                    {
                        "talker": "코미",
                        "content": "삼성전자 소식입니다.",
                    }
                ]
            ),
        ]
    )
    ai_client.generate_personal_sections = AsyncMock(
        return_value=PersonalSectionsAiResponse(
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
                        "content": "이어서 종목 소식입니다.",
                    }
                ]
            ],
            closing=[
                {
                    "talker": "코미",
                    "content": "오늘 브리핑을 마치겠습니다.",
                }
            ],
        )
    )
    news_repository = NewsRepository(session)
    section_repository = SectionRepository(session)
    service = ScriptGenerationService(
        session=session,
        user_interest_repository=UserInterestRepository(session),
        script_repository=ScriptRepository(
            session
        ),
        common_section_service=CommonSectionService(
            news_repository=news_repository,
            target_repository=TargetRepository(session),
            section_repository=section_repository,
            ai_client=ai_client,
        ),
        personal_section_service=PersonalSectionService(
            section_repository=section_repository,
            price_repository=PriceRepository(session),
            target_repository=TargetRepository(session),
            ai_client=ai_client,
        ),
    )
    return service, ai_client


@pytest.mark.asyncio
async def test_full_generation_and_completed_document_reuse(
    session: Session,
) -> None:
    add_generation_data(session)
    service, ai_client = create_generation_service(session)

    first_response = await service.generate(
        [USER_ID],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert first_response.failures == []
    assert first_response.scripts[0].reused is False
    script = session.scalar(
        select(Script).where(
            Script.user_id == USER_ID
        )
    )
    assert script is not None
    assert script.status == ScriptStatus.COMPLETED
    script_sections = ScriptRepository(
        session
    ).find_sections(script.id)
    assert [item.section_type for item in script_sections] == [
        SectionType.OPENING,
        SectionType.INDUSTRY,
        SectionType.BRIDGE,
        SectionType.STOCK,
        SectionType.CLOSING,
    ]
    assert ai_client.generate_common_section.await_count == 2
    ai_client.generate_personal_sections.assert_awaited_once()
    personal_source = (
        ai_client.generate_personal_sections.await_args.args[0]
    )
    assert "대상: 반도체" in personal_source
    assert "지수값: 12345.67" in personal_source
    assert "등락: 1.01% 하락" in personal_source
    assert "대상: 삼성전자" in personal_source
    assert "종가: 270000원" in personal_source
    assert "등락: 3.65% 상승" in personal_source

    second_response = await service.generate(
        [USER_ID],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert second_response.failures == []
    assert second_response.scripts[0].script_id == script.id
    assert second_response.scripts[0].reused is True
    assert ai_client.generate_common_section.await_count == 2
    ai_client.generate_personal_sections.assert_awaited_once()
