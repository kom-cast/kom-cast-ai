from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from script_app.models import StockNewsSummary, StockScript

class NewsRepository:

    def __init__(self, session: Session):
        self.session = session
    
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
    
