from datetime import datetime

from sqlalchemy import Select, select
from sqlalchemy.orm import Session, joinedload

from models import News, NewsSummary, Script


class NewsRepository:
    def save_all(
        self,
        session: Session,
        news_list: list[News],
    ) -> None:
        session.add_all(news_list)

    def count(self, session: Session) -> int:
        return len(session.scalars(select(News)).all())

    def find_all(self, session: Session) -> list[News]:
        statement = select(News).order_by(News.published_at.desc())
        return list(session.scalars(statement).all())

    def find_unsummarized(self, session: Session) -> list[News]:
        """
        summary가 존재하지 않는 뉴스만 조회한다.

        SQL 관점:
        SELECT *
        FROM news n
        WHERE NOT EXISTS (
            SELECT 1
            FROM news_summary s
            WHERE s.news_id = n.id
        )
        """
        statement = (
            select(News)
            .outerjoin(NewsSummary)
            .where(NewsSummary.id.is_(None))
            .order_by(News.published_at.asc())
        )

        return list(session.scalars(statement).all())

    def find_by_filter(
        self,
        session: Session,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        topic: str | None = None,
    ) -> list[News]:
        statement: Select = (
            select(News)
            .options(joinedload(News.summary))
            .where(NewsSummary.id.is_not(None))
        )

        if start_at is not None:
            statement = statement.where(News.published_at >= start_at)

        if end_at is not None:
            statement = statement.where(News.published_at <= end_at)

        if topic:
            statement = statement.where(News.topic == topic)

        statement = statement.order_by(News.published_at.asc())

        return list(session.scalars(statement).unique().all())


class SummaryRepository:
    def save(
        self,
        session: Session,
        summary: NewsSummary,
    ) -> None:
        session.add(summary)

    def find_all(self, session: Session) -> list[NewsSummary]:
        statement = (
            select(NewsSummary)
            .options(joinedload(NewsSummary.news))
            .order_by(NewsSummary.created_at.desc())
        )

        return list(session.scalars(statement).unique().all())


class ScriptRepository:
    def save(
        self,
        session: Session,
        script: Script,
    ) -> None:
        session.add(script)

    def find_latest(self, session: Session) -> Script | None:
        statement = (
            select(Script)
            .order_by(Script.created_at.desc())
            .limit(1)
        )

        return session.scalar(statement)
