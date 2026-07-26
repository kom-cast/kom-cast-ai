from datetime import date, datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from script_app.database import Base
from script_app.models import (
    Industry,
    NewsArticle,
    NewsIndustryMapping,
    NewsStockMapping,
    Section,
    SectionLine,
    SectionTargetType,
    SectionType,
    ScriptDocument,
    ScriptDocumentStatus,
    ScriptSection,
    Stock,
    StockNewsSummary,
    StockScript,
    UserIndustry,
    UserStock,
)


USER_ID = UUID("3ad697a8-8d7d-4f80-a66f-04d994a89611")


@pytest.fixture
def session():
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


def test_tables_are_created() -> None:
    test_engine = create_engine(
        "sqlite:///:memory:",
    )

    Base.metadata.create_all(bind=test_engine)

    inspector = inspect(test_engine)
    table_names = inspector.get_table_names()

    assert "industries" in table_names
    assert "stocks" in table_names
    assert "user_stocks" in table_names
    assert "user_industries" in table_names
    assert "news_articles" in table_names
    assert "news_stock_mappings" in table_names
    assert "news_industry_mappings" in table_names
    assert "sections" in table_names
    assert "section_lines" in table_names
    assert "script_documents" in table_names
    assert "script_sections" in table_names
    assert "stock_news_summaries" in table_names
    assert "stock_scripts" in table_names


def add_stock_master_data(session) -> None:
    session.add(
        Industry(
            industry_code="SEMI",
            industry_name="반도체",
        )
    )
    session.add(
        Stock(
            stock_code="005930",
            corp_code="00126380",
            corp_name="삼성전자",
            dart_modify_date=date(2026, 7, 22),
            industry_code="SEMI",
        )
    )
    session.commit()


def test_save_stock_and_industry(session) -> None:
    add_stock_master_data(session)

    stock = session.get(Stock, "005930")
    industry = session.get(Industry, "SEMI")

    assert stock is not None
    assert stock.corp_name == "삼성전자"
    assert stock.industry_code == "SEMI"
    assert industry is not None
    assert industry.industry_name == "반도체"


def test_save_user_stock_and_industry(session) -> None:
    add_stock_master_data(session)
    user_stock = UserStock(
        user_id=USER_ID,
        stock_code="005930",
        interest_type="HOLDING",
    )
    user_industry = UserIndustry(
        user_id=USER_ID,
        industry_code="SEMI",
    )

    session.add_all([user_stock, user_industry])
    session.commit()

    assert user_stock.id is not None
    assert user_industry.id is not None


def test_duplicate_user_stock_is_rejected(session) -> None:
    add_stock_master_data(session)
    session.add(
        UserStock(
            user_id=USER_ID,
            stock_code="005930",
            interest_type="HOLDING",
        )
    )
    session.commit()

    session.add(
        UserStock(
            user_id=USER_ID,
            stock_code="005930",
            interest_type="INTEREST",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_duplicate_user_industry_is_rejected(session) -> None:
    add_stock_master_data(session)
    session.add(
        UserIndustry(
            user_id=USER_ID,
            industry_code="SEMI",
        )
    )
    session.commit()

    session.add(
        UserIndustry(
            user_id=USER_ID,
            industry_code="SEMI",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def add_news_article(session) -> NewsArticle:
    news_article = NewsArticle(
        source="테스트 언론사",
        news_date=date(2026, 7, 22),
        news_code="NEWS-001",
        published_at=datetime(
            2026,
            7,
            22,
            9,
            0,
            tzinfo=timezone.utc,
        ),
        title="반도체 신규 투자 발표",
        body="반도체 생산 시설에 대한 신규 투자 계획을 발표했다.",
        press_code=100,
    )
    session.add(news_article)
    session.commit()
    return news_article


def test_save_news_article_and_target_mappings(session) -> None:
    add_stock_master_data(session)
    news_article = add_news_article(session)
    stock_mapping = NewsStockMapping(
        news_id=news_article.id,
        stock_code="005930",
    )
    industry_mapping = NewsIndustryMapping(
        news_id=news_article.id,
        industry_code="SEMI",
    )

    session.add_all([stock_mapping, industry_mapping])
    session.commit()

    assert news_article.id is not None
    assert stock_mapping.news_id == news_article.id
    assert industry_mapping.news_id == news_article.id


def test_duplicate_news_stock_mapping_is_rejected(session) -> None:
    add_stock_master_data(session)
    news_article = add_news_article(session)
    session.add(
        NewsStockMapping(
            news_id=news_article.id,
            stock_code="005930",
        )
    )
    session.commit()

    session.add(
        NewsStockMapping(
            news_id=news_article.id,
            stock_code="005930",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_duplicate_news_industry_mapping_is_rejected(session) -> None:
    add_stock_master_data(session)
    news_article = add_news_article(session)
    session.add(
        NewsIndustryMapping(
            news_id=news_article.id,
            industry_code="SEMI",
        )
    )
    session.commit()

    session.add(
        NewsIndustryMapping(
            news_id=news_article.id,
            industry_code="SEMI",
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def create_stock_section(session) -> Section:
    add_stock_master_data(session)
    section = Section(
        section_type=SectionType.STOCK,
        target_type=SectionTargetType.STOCK,
        stock_code="005930",
        industry_code=None,
        period_start=datetime(
            2026,
            7,
            22,
            tzinfo=timezone.utc,
        ),
        period_end=datetime(
            2026,
            7,
            23,
            tzinfo=timezone.utc,
        ),
    )
    session.add(section)
    session.commit()
    return section


def test_save_section_and_lines(session) -> None:
    section = create_stock_section(session)
    lines = [
        SectionLine(
            section_id=section.id,
            line_order=1,
            talker="코스",
            content="오늘 살펴볼 종목은 삼성전자입니다.",
        ),
        SectionLine(
            section_id=section.id,
            line_order=2,
            talker="코미",
            content="주요 뉴스부터 살펴보겠습니다.",
        ),
    ]

    session.add_all(lines)
    session.commit()

    assert section.id is not None
    assert [line.line_order for line in lines] == [1, 2]


def test_duplicate_section_line_order_is_rejected(session) -> None:
    section = create_stock_section(session)
    session.add_all(
        [
            SectionLine(
                section_id=section.id,
                line_order=1,
                talker="코스",
                content="첫 번째 발화",
            ),
            SectionLine(
                section_id=section.id,
                line_order=1,
                talker="코미",
                content="중복 순서 발화",
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_duplicate_stock_section_reuse_key_is_rejected(session) -> None:
    first_section = create_stock_section(session)
    session.add(
        Section(
            section_type=SectionType.STOCK,
            target_type=SectionTargetType.STOCK,
            stock_code=first_section.stock_code,
            industry_code=None,
            period_start=first_section.period_start,
            period_end=first_section.period_end,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_section_target_columns_must_match_section_type(session) -> None:
    add_stock_master_data(session)
    session.add(
        Section(
            section_type=SectionType.STOCK,
            target_type=SectionTargetType.INDUSTRY,
            stock_code="005930",
            industry_code=None,
            period_start=datetime(
                2026,
                7,
                22,
                tzinfo=timezone.utc,
            ),
            period_end=datetime(
                2026,
                7,
                23,
                tzinfo=timezone.utc,
            ),
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def create_script_document(session) -> ScriptDocument:
    document = ScriptDocument(
        user_id=USER_ID,
        period_start=datetime(
            2026,
            7,
            22,
            tzinfo=timezone.utc,
        ),
        period_end=datetime(
            2026,
            7,
            23,
            tzinfo=timezone.utc,
        ),
        status=ScriptDocumentStatus.GENERATING,
    )
    session.add(document)
    session.commit()
    return document


def test_save_script_document_and_ordered_sections(session) -> None:
    document = create_script_document(session)
    section = create_stock_section(session)
    script_section = ScriptSection(
        document_id=document.id,
        section_id=section.id,
        section_order=1,
        section_type=SectionType.STOCK,
    )

    session.add(script_section)
    document.status = ScriptDocumentStatus.COMPLETED
    session.commit()

    assert document.id is not None
    assert document.status == ScriptDocumentStatus.COMPLETED
    assert script_section.id is not None
    assert script_section.section_order == 1


def test_duplicate_script_document_period_is_rejected(session) -> None:
    first_document = create_script_document(session)
    session.add(
        ScriptDocument(
            user_id=first_document.user_id,
            period_start=first_document.period_start,
            period_end=first_document.period_end,
            status=ScriptDocumentStatus.GENERATING,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_duplicate_script_section_order_is_rejected(session) -> None:
    document = create_script_document(session)
    section = create_stock_section(session)
    session.add_all(
        [
            ScriptSection(
                document_id=document.id,
                section_id=section.id,
                section_order=1,
                section_type=SectionType.STOCK,
            ),
            ScriptSection(
                document_id=document.id,
                section_id=section.id,
                section_order=1,
                section_type=SectionType.STOCK,
            ),
        ]
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_script_section_order_must_be_positive(session) -> None:
    document = create_script_document(session)
    section = create_stock_section(session)
    session.add(
        ScriptSection(
            document_id=document.id,
            section_id=section.id,
            section_order=0,
            section_type=SectionType.STOCK,
        )
    )

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()


def test_save_stock_news_summary(session) -> None:
    news_summary = StockNewsSummary(
        title="A사 신규 제품 공개",
        summary_content="A사가 신규 제품을 공개했다.",
        stock_id=1,
        news_published_at=datetime(
            2026,
            7,
            16,
            9,
            0,
            tzinfo=timezone.utc,
        ),
    )

    session.add(news_summary)
    session.commit()

    assert news_summary.id is not None
    assert news_summary.stock_id == 1
    assert news_summary.title == "A사 신규 제품 공개"


def test_save_stock_script(session) -> None:
    stock_script = StockScript(
        stock_id=1,
        start_at=datetime(2026, 7, 16, 0, 0,),
        end_at=datetime(2026, 7, 17, 0, 0,),
        script_content="테스트 스크립트입니다.",
    )

    session.add(stock_script)
    session.commit()

    assert stock_script.id is not None
    assert stock_script.created_at is not None


def test_duplicate_stock_script_is_rejected(session) -> None:
    start_at=datetime(2026, 7, 16, 0, 0,)
    end_at=datetime(2026, 7, 17, 0, 0,)

    first_script = StockScript(
        stock_id=1,
        start_at=start_at,
        end_at=end_at,
        script_content="첫 번째 스크립트",
    )

    second_script = StockScript(
        stock_id=1,
        start_at=start_at,
        end_at=end_at,
        script_content="두 번째 스크립트",
    )

    session.add(first_script)
    session.commit()

    session.add(second_script)

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()
