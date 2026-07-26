from datetime import datetime, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from script_app.database import Base
from script_app.models import StockNewsSummary
from script_app.repositories import NewsRepository


@pytest.fixture
def session() -> Session:
    """
    각 테스트마다 독립적인 인메모리 SQLite DB를 생성한다.
    테스트가 끝나면 DB 세션과 테이블을 정리한다.
    """
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


def create_news_summary(
    *,
    title: str,
    stock_id: int,
    published_at: datetime,
) -> StockNewsSummary:
    """
    테스트용 뉴스 요약 객체를 생성하는 헬퍼 함수다.
    """
    return StockNewsSummary(
        title=title,
        summary_content=f"{title}의 요약 내용",
        stock_id=stock_id,
        news_published_at=published_at,
    )


class TestNewsRepository:
    def test_find_news_summaries_returns_news_in_period(
        self,
        session: Session,
    ) -> None:
        # given
        session.add_all(
            [
                create_news_summary(
                    title="삼성전자 첫 번째 뉴스",
                    stock_id=1,
                    published_at=datetime(2026, 7, 16, 9, 0),
                ),
                create_news_summary(
                    title="삼성전자 두 번째 뉴스",
                    stock_id=1,
                    published_at=datetime(2026, 7, 16, 15, 0),
                ),
            ]
        )
        session.commit()

        repository = NewsRepository(session)

        # when
        result = repository.find_news_summaries(
            stock_id=1,
            start=datetime(2026, 7, 16,),
            end=datetime(2026, 7, 17,),
        )

        # then
        assert len(result) == 2
        assert result[0].title == "삼성전자 첫 번째 뉴스"
        assert result[1].title == "삼성전자 두 번째 뉴스"

    def test_find_news_summaries_excludes_other_stocks(
        self,
        session: Session,
    ) -> None:
        # given
        session.add_all(
            [
                create_news_summary(
                    title="삼성전자 뉴스",
                    stock_id=1,
                    published_at=datetime(2026, 7, 16, 9, 0,),
                ),
                create_news_summary(
                    title="SK하이닉스 뉴스",
                    stock_id=2,
                    published_at=datetime(2026, 7, 16, 10, 0,),
                ),
            ]
        )
        session.commit()

        repository = NewsRepository(session)

        # when
        result = repository.find_news_summaries(
            stock_id=1,
            start=datetime(2026, 7, 16,),
            end=datetime(2026, 7, 17,),
        )

        # then
        assert len(result) == 1
        assert result[0].title == "삼성전자 뉴스"
        assert result[0].stock_id == 1

    def test_find_news_summaries_excludes_news_outside_period(
        self,
        session: Session,
    ) -> None:
        # given
        session.add_all(
            [
                create_news_summary(
                    title="조회 기간 이전 뉴스",
                    stock_id=1,
                    published_at=datetime(2026, 7, 15, 23, 59,),
                ),
                create_news_summary(
                    title="조회 기간 내부 뉴스",
                    stock_id=1,
                    published_at=datetime(2026, 7, 16, 12, 0,),
                ),
                create_news_summary(
                    title="조회 기간 이후 뉴스",
                    stock_id=1,
                    published_at=datetime(2026, 7, 17, 1, 0,),
                ),
            ]
        )
        session.commit()

        repository = NewsRepository(session)

        # when
        result = repository.find_news_summaries(
            stock_id=1,
            start=datetime(2026, 7, 16,),
            end=datetime(2026, 7, 17,),
        )

        # then
        assert len(result) == 1
        assert result[0].title == "조회 기간 내부 뉴스"

    def test_find_news_summaries_includes_start_time(
        self,
        session: Session,
    ) -> None:
        # given
        start = datetime(2026, 7, 16,)

        session.add(
            create_news_summary(
                title="시작 시각 뉴스",
                stock_id=1,
                published_at=start,
            )
        )
        session.commit()

        repository = NewsRepository(session)

        # when
        result = repository.find_news_summaries(
            stock_id=1,
            start=start,
            end=datetime(2026, 7, 17,),
        )

        # then
        assert len(result) == 1
        assert result[0].title == "시작 시각 뉴스"

    def test_find_news_summaries_excludes_end_time(
        self,
        session: Session,
    ) -> None:
        # given
        end = datetime(2026, 7, 17,)

        session.add_all(
            [
                create_news_summary(
                    title="종료 직전 뉴스",
                    stock_id=1,
                    published_at=end - timedelta(seconds=1)
                ),
                create_news_summary(
                    title="종료 시각 뉴스",
                    stock_id=1,
                    published_at=end,
                ),
            ]
        )
        session.commit()

        repository = NewsRepository(session)

        # when
        result = repository.find_news_summaries(
            stock_id=1,
            start=datetime(2026, 7, 16,),
            end=end,
        )

        # then
        assert len(result) == 1
        assert result[0].title == "종료 직전 뉴스"

    def test_find_news_summaries_returns_empty_list_when_no_news(
        self,
        session: Session,
    ) -> None:
        # given
        repository = NewsRepository(session)

        # when
        result = repository.find_news_summaries(
            stock_id=1,
            start=datetime(2026, 7, 16,),
            end=datetime(2026, 7, 17,),
        )

        # then
        assert result == []