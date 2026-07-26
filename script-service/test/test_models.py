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
