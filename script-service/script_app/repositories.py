from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from script_app.models import (
    NewsArticle,
    NewsIndustryMapping,
    NewsStockMapping,
    StockNewsSummary,
    StockScript,
    UserIndustry,
    UserStock,
)


@dataclass
class UserInterestTargets:
    stock_codes: list[str] = field(default_factory=list)
    industry_codes: list[str] = field(default_factory=list)


class UserInterestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_user_ids(
        self,
        user_ids: list[UUID],
    ) -> dict[UUID, UserInterestTargets]:
        unique_user_ids = list(dict.fromkeys(user_ids))
        targets_by_user = {
            user_id: UserInterestTargets()
            for user_id in unique_user_ids
        }

        if not unique_user_ids:
            return targets_by_user

        stock_stmt = (
            select(
                UserStock.user_id,
                UserStock.stock_code,
            )
            .where(UserStock.user_id.in_(unique_user_ids))
            .order_by(
                UserStock.user_id,
                UserStock.stock_code,
            )
        )

        for user_id, stock_code in self.session.execute(stock_stmt):
            targets_by_user[user_id].stock_codes.append(stock_code)

        industry_stmt = (
            select(
                UserIndustry.user_id,
                UserIndustry.industry_code,
            )
            .where(UserIndustry.user_id.in_(unique_user_ids))
            .order_by(
                UserIndustry.user_id,
                UserIndustry.industry_code,
            )
        )

        for user_id, industry_code in self.session.execute(
            industry_stmt
        ):
            targets_by_user[user_id].industry_codes.append(
                industry_code
            )

        return targets_by_user


class NewsRepository:

    def __init__(self, session: Session):
        self.session = session

    def find_by_stock_codes(
        self,
        stock_codes: list[str],
        start_at: datetime,
        end_at: datetime,
    ) -> dict[str, list[NewsArticle]]:
        unique_stock_codes = list(dict.fromkeys(stock_codes))
        news_by_stock = {
            stock_code: []
            for stock_code in unique_stock_codes
        }

        if not unique_stock_codes:
            return news_by_stock

        stmt = (
            select(
                NewsStockMapping.stock_code,
                NewsArticle,
            )
            .join(
                NewsArticle,
                NewsArticle.id == NewsStockMapping.news_id,
            )
            .where(
                NewsStockMapping.stock_code.in_(
                    unique_stock_codes
                ),
                NewsArticle.published_at >= start_at,
                NewsArticle.published_at < end_at,
            )
            .order_by(
                NewsStockMapping.stock_code,
                NewsArticle.published_at,
                NewsArticle.id,
            )
        )

        for stock_code, news_article in self.session.execute(stmt):
            news_by_stock[stock_code].append(news_article)

        return news_by_stock

    def find_by_industry_codes(
        self,
        industry_codes: list[str],
        start_at: datetime,
        end_at: datetime,
    ) -> dict[str, list[NewsArticle]]:
        unique_industry_codes = list(
            dict.fromkeys(industry_codes)
        )
        news_by_industry = {
            industry_code: []
            for industry_code in unique_industry_codes
        }

        if not unique_industry_codes:
            return news_by_industry

        stmt = (
            select(
                NewsIndustryMapping.industry_code,
                NewsArticle,
            )
            .join(
                NewsArticle,
                NewsArticle.id == NewsIndustryMapping.news_id,
            )
            .where(
                NewsIndustryMapping.industry_code.in_(
                    unique_industry_codes
                ),
                NewsArticle.published_at >= start_at,
                NewsArticle.published_at < end_at,
            )
            .order_by(
                NewsIndustryMapping.industry_code,
                NewsArticle.published_at,
                NewsArticle.id,
            )
        )

        for industry_code, news_article in self.session.execute(
            stmt
        ):
            news_by_industry[industry_code].append(news_article)

        return news_by_industry
    
    def find_news_summaries(
        self,
        stock_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> list[StockNewsSummary]:

        stmt = (
            select(StockNewsSummary)
            .where(
                StockNewsSummary.stock_id == stock_id,
                StockNewsSummary.news_published_at >= start_at,
                StockNewsSummary.news_published_at < end_at,
            )
            .order_by(
                StockNewsSummary.news_published_at
            )
        )

        return list(
            self.session.scalars(stmt)
        )

class ScriptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self,
        stock_script: StockScript,
    ) -> StockScript:
        self.session.add(stock_script)
        self.session.commit()
        self.session.refresh(stock_script)

        return stock_script
    
