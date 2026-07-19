from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import StockNewsSummary

class NewsRepository:

    def __init__(self, session: Session):
        self.session = session
    
    def find_news_summaries(
        self,
        stock_id: int,
        start: datetime,
        end: datetime,
    ) -> list[StockNewsSummary]:

        stmt = (
            select(StockNewsSummary)
            .where(
                StockNewsSummary.stock_id == stock_id,
                StockNewsSummary.news_published_at >= start,
                StockNewsSummary.news_published_at < end,
            )
            .order_by(
                StockNewsSummary.news_published_at
            )
        )

        return list(
            self.session.scalars(stmt)
        )
