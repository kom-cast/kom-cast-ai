from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.models import StockNewsSummary, StockScript


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

    assert "stock_news_summaries" in table_names
    assert "stock_scripts" in table_names


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
        period_start=datetime(
            2026,
            7,
            16,
            0,
            0,
            tzinfo=timezone.utc,
        ),
        period_end=datetime(
            2026,
            7,
            17,
            0,
            0,
            tzinfo=timezone.utc,
        ),
        script_content="테스트 스크립트입니다.",
    )

    session.add(stock_script)
    session.commit()

    assert stock_script.id is not None
    assert stock_script.created_at is not None


def test_duplicate_stock_script_is_rejected(session) -> None:
    period_start = datetime(
        2026,
        7,
        16,
        0,
        0,
        tzinfo=timezone.utc,
    )

    period_end = datetime(
        2026,
        7,
        17,
        0,
        0,
        tzinfo=timezone.utc,
    )

    first_script = StockScript(
        stock_id=1,
        period_start=period_start,
        period_end=period_end,
        script_content="첫 번째 스크립트",
    )

    second_script = StockScript(
        stock_id=1,
        period_start=period_start,
        period_end=period_end,
        script_content="두 번째 스크립트",
    )

    session.add(first_script)
    session.commit()

    session.add(second_script)

    with pytest.raises(IntegrityError):
        session.commit()

    session.rollback()
