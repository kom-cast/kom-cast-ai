from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from script_app.database import Base
from script_app.models import Industry, Stock, UserIndustry, UserStock
from script_app.repositories import (
    TargetRepository,
    UserInterestRepository,
)


USER_ID_1 = UUID("3ad697a8-8d7d-4f80-a66f-04d994a89611")
USER_ID_2 = UUID("852471a5-f181-47f9-b526-079eef611ed8")
USER_ID_WITHOUT_TARGETS = UUID(
    "f516d536-a85d-441b-81c8-89948581ed83"
)


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


def add_interest_data(session: Session) -> None:
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
            UserStock(
                user_id=USER_ID_1,
                stock_code="005930",
                interest_type="HOLDING",
            ),
            UserStock(
                user_id=USER_ID_2,
                stock_code="000660",
                interest_type="INTEREST",
            ),
            UserStock(
                user_id=USER_ID_2,
                stock_code="005930",
                interest_type="INTEREST",
            ),
            UserIndustry(
                user_id=USER_ID_1,
                industry_code="DISPLAY",
            ),
            UserIndustry(
                user_id=USER_ID_2,
                industry_code="SEMI",
            ),
        ]
    )
    session.commit()


def test_find_targets_for_multiple_users(session: Session) -> None:
    add_interest_data(session)
    repository = UserInterestRepository(session)

    result = repository.find_by_user_ids(
        [USER_ID_1, USER_ID_2]
    )

    assert result[USER_ID_1].stock_codes == ["005930"]
    assert result[USER_ID_1].industry_codes == ["DISPLAY"]
    assert result[USER_ID_2].stock_codes == ["000660", "005930"]
    assert result[USER_ID_2].industry_codes == ["SEMI"]


def test_find_targets_includes_users_without_targets(
    session: Session,
) -> None:
    add_interest_data(session)
    repository = UserInterestRepository(session)

    result = repository.find_by_user_ids(
        [USER_ID_1, USER_ID_WITHOUT_TARGETS]
    )

    assert list(result) == [USER_ID_1, USER_ID_WITHOUT_TARGETS]
    assert result[USER_ID_WITHOUT_TARGETS].stock_codes == []
    assert result[USER_ID_WITHOUT_TARGETS].industry_codes == []


def test_find_targets_removes_duplicate_user_ids(
    session: Session,
) -> None:
    add_interest_data(session)
    repository = UserInterestRepository(session)

    result = repository.find_by_user_ids(
        [USER_ID_2, USER_ID_1, USER_ID_2]
    )

    assert list(result) == [USER_ID_2, USER_ID_1]


def test_find_targets_returns_empty_result_for_empty_input(
    session: Session,
) -> None:
    repository = UserInterestRepository(session)

    result = repository.find_by_user_ids([])

    assert result == {}


def test_find_target_master_names(session: Session) -> None:
    add_interest_data(session)
    repository = TargetRepository(session)

    stocks = repository.find_stocks(["005930", "000660"])
    industries = repository.find_industries(
        ["SEMI", "DISPLAY"]
    )

    assert stocks["005930"].corp_name == "삼성전자"
    assert stocks["000660"].corp_name == "SK하이닉스"
    assert industries["SEMI"].industry_name == "반도체"
    assert industries["DISPLAY"].industry_name == "디스플레이"


def test_target_master_lookup_handles_empty_input(
    session: Session,
) -> None:
    repository = TargetRepository(session)

    assert repository.find_stocks([]) == {}
    assert repository.find_industries([]) == {}
