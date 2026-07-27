from datetime import datetime, timezone
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from script_app.database import Base
from script_app.models import (
    Industry,
    IndustryPrice,
    MarketPrice,
    Stock,
)
from script_app.repositories import PriceRepository


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
        test_session.add_all(
            [
                Industry(
                    industry_code="SEMI",
                    industry_name="반도체",
                ),
                Stock(
                    stock_code="005930",
                    corp_code="00126380",
                    corp_name="삼성전자",
                    industry_code="SEMI",
                ),
            ]
        )
        test_session.commit()
        yield test_session

    Base.metadata.drop_all(bind=test_engine)


def add_market_price(
    session,
    *,
    traded_at: datetime,
    close_price: str,
    provider: str = "KOSCOM",
    interval: str = "DAILY",
) -> MarketPrice:
    now = datetime.now(timezone.utc)
    price = MarketPrice(
        stock_code="005930",
        traded_at=traded_at,
        interval=interval,
        open_price=Decimal(close_price),
        high_price=Decimal(close_price),
        low_price=Decimal(close_price),
        close_price=Decimal(close_price),
        volume=1,
        change_rate=Decimal("1.00"),
        trading_value=1,
        market_cap=1,
        vwap=None,
        provider=provider,
        raw_external_id=(
            f"{provider}:{interval}:{traded_at.isoformat()}"
        ),
        created_at=now,
        updated_at=now,
    )
    session.add(price)
    session.commit()
    return price


def add_industry_price(
    session,
    *,
    traded_at: datetime,
    index_value: str,
    provider: str = "KOSCOM",
) -> IndustryPrice:
    now = datetime.now(timezone.utc)
    price = IndustryPrice(
        industry_code="SEMI",
        traded_at=traded_at,
        index_value=Decimal(index_value),
        change_amount=Decimal("10.00"),
        change_rate=Decimal("1.00"),
        open_value=None,
        high_value=None,
        low_value=None,
        volume=1,
        trading_value=1,
        market_cap=None,
        market_cap_free_float=None,
        shares_outstanding=None,
        foreign_ownership_rate=None,
        short_sale_volume=None,
        short_sale_value=None,
        provider=provider,
        raw_external_id=f"{provider}:{traded_at.isoformat()}",
        created_at=now,
        updated_at=now,
    )
    session.add(price)
    session.commit()
    return price


def test_find_latest_stock_price_before_as_of(session) -> None:
    add_market_price(
        session,
        traded_at=datetime(2026, 7, 21, 15, tzinfo=timezone.utc),
        close_price="260000",
    )
    latest = add_market_price(
        session,
        traded_at=datetime(2026, 7, 22, 15, tzinfo=timezone.utc),
        close_price="270000",
    )
    add_market_price(
        session,
        traded_at=datetime(2026, 7, 23, 15, tzinfo=timezone.utc),
        close_price="280000",
    )

    result = PriceRepository(session).find_latest_stock_prices(
        ["005930", "005930"],
        as_of=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )

    assert result == {"005930": latest}


def test_stock_price_uses_daily_koscom_data(session) -> None:
    expected = add_market_price(
        session,
        traded_at=datetime(2026, 7, 21, 15, tzinfo=timezone.utc),
        close_price="260000",
    )
    add_market_price(
        session,
        traded_at=datetime(2026, 7, 22, 15, tzinfo=timezone.utc),
        close_price="270000",
        interval="MINUTE",
    )
    add_market_price(
        session,
        traded_at=datetime(2026, 7, 22, 16, tzinfo=timezone.utc),
        close_price="280000",
        provider="OTHER",
    )

    result = PriceRepository(session).find_latest_stock_prices(
        ["005930"],
        as_of=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )

    assert result == {"005930": expected}


def test_find_latest_industry_price_before_as_of(session) -> None:
    add_industry_price(
        session,
        traded_at=datetime(2026, 7, 21, 15, tzinfo=timezone.utc),
        index_value="12000.00",
    )
    latest = add_industry_price(
        session,
        traded_at=datetime(2026, 7, 22, 15, tzinfo=timezone.utc),
        index_value="12345.67",
    )
    add_industry_price(
        session,
        traded_at=datetime(2026, 7, 22, 16, tzinfo=timezone.utc),
        index_value="13000.00",
        provider="OTHER",
    )

    result = PriceRepository(session).find_latest_industry_prices(
        ["SEMI"],
        as_of=datetime(2026, 7, 23, tzinfo=timezone.utc),
    )

    assert result == {"SEMI": latest}


def test_price_queries_handle_empty_input(session) -> None:
    repository = PriceRepository(session)
    as_of = datetime(2026, 7, 23, tzinfo=timezone.utc)

    assert repository.find_latest_stock_prices([], as_of) == {}
    assert repository.find_latest_industry_prices([], as_of) == {}
