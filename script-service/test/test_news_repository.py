from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from script_app.database import Base
from script_app.models import (
    Industry,
    NewsArticle,
    NewsIndustryMapping,
    NewsStockMapping,
    Stock,
)
from script_app.repositories import NewsRepository


START_AT = datetime(2026, 7, 22, tzinfo=timezone.utc)
END_AT = datetime(2026, 7, 23, tzinfo=timezone.utc)


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


def add_master_data(session: Session) -> None:
    session.add_all(
        [
            Industry(
                industry_code="DISPLAY",
                industry_name="디스플레이",
            ),
            Industry(
                industry_code="SEMI",
                industry_name="반도체",
            ),
            Stock(
                stock_code="000660",
                corp_code="00164779",
                corp_name="SK하이닉스",
                industry_code="SEMI",
            ),
            Stock(
                stock_code="005930",
                corp_code="00126380",
                corp_name="삼성전자",
                industry_code="SEMI",
            ),
        ]
    )
    session.commit()


def add_news(
    session: Session,
    *,
    title: str,
    published_at: datetime,
    stock_codes: list[str],
    industry_codes: list[str],
) -> NewsArticle:
    article = NewsArticle(
        source="테스트 언론사",
        news_date=published_at.date(),
        published_at=published_at,
        title=title,
        body=f"{title} 요약",
    )
    session.add(article)
    session.flush()

    session.add_all(
        [
            NewsStockMapping(
                news_id=article.id,
                stock_code=stock_code,
            )
            for stock_code in stock_codes
        ]
    )
    session.add_all(
        [
            NewsIndustryMapping(
                news_id=article.id,
                industry_code=industry_code,
            )
            for industry_code in industry_codes
        ]
    )
    session.commit()
    return article


def test_find_news_by_stock_codes_groups_and_orders_results(
    session: Session,
) -> None:
    add_master_data(session)
    add_news(
        session,
        title="두 번째 뉴스",
        published_at=START_AT + timedelta(hours=2),
        stock_codes=["005930"],
        industry_codes=[],
    )
    add_news(
        session,
        title="첫 번째 뉴스",
        published_at=START_AT + timedelta(hours=1),
        stock_codes=["000660", "005930"],
        industry_codes=[],
    )
    repository = NewsRepository(session)

    result = repository.find_by_stock_codes(
        ["005930", "000660", "035420"],
        start_at=START_AT,
        end_at=END_AT,
    )

    assert [news.title for news in result["005930"]] == [
        "첫 번째 뉴스",
        "두 번째 뉴스",
    ]
    assert [news.title for news in result["000660"]] == [
        "첫 번째 뉴스"
    ]
    assert result["035420"] == []


def test_find_news_by_industry_codes_uses_direct_mappings(
    session: Session,
) -> None:
    add_master_data(session)
    add_news(
        session,
        title="반도체 뉴스",
        published_at=START_AT + timedelta(hours=1),
        stock_codes=[],
        industry_codes=["SEMI"],
    )
    repository = NewsRepository(session)

    result = repository.find_by_industry_codes(
        ["DISPLAY", "SEMI"],
        start_at=START_AT,
        end_at=END_AT,
    )

    assert result["DISPLAY"] == []
    assert [news.title for news in result["SEMI"]] == [
        "반도체 뉴스"
    ]


def test_news_period_includes_start_and_excludes_end(
    session: Session,
) -> None:
    add_master_data(session)
    add_news(
        session,
        title="시작 시각 뉴스",
        published_at=START_AT,
        stock_codes=["005930"],
        industry_codes=[],
    )
    add_news(
        session,
        title="종료 시각 뉴스",
        published_at=END_AT,
        stock_codes=["005930"],
        industry_codes=[],
    )
    repository = NewsRepository(session)

    result = repository.find_by_stock_codes(
        ["005930"],
        start_at=START_AT,
        end_at=END_AT,
    )

    assert [news.title for news in result["005930"]] == [
        "시작 시각 뉴스"
    ]


def test_news_bulk_queries_handle_empty_input(session: Session) -> None:
    repository = NewsRepository(session)

    assert repository.find_by_stock_codes(
        [],
        start_at=START_AT,
        end_at=END_AT,
    ) == {}
    assert repository.find_by_industry_codes(
        [],
        start_at=START_AT,
        end_at=END_AT,
    ) == {}
