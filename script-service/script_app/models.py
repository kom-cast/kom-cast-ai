from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from script_app.database import Base


class Industry(Base):
    __tablename__ = "industries"

    industry_code: Mapped[str] = mapped_column(
        String(50),
        primary_key=True,
    )

    industry_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )


class Stock(Base):
    __tablename__ = "stocks"

    stock_code: Mapped[str] = mapped_column(
        String(20),
        primary_key=True,
    )

    corp_code: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        unique=True,
    )

    corp_name: Mapped[str] = mapped_column(
        String(200),
        nullable=False,
    )

    dart_modify_date: Mapped[date | None] = mapped_column(
        nullable=True,
    )

    industry_code: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("industries.industry_code"),
        nullable=True,
    )


class UserStock(Base):
    __tablename__ = "user_stocks"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        nullable=False,
    )

    stock_code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stocks.stock_code"),
        nullable=False,
    )

    interest_type: Mapped[str] = mapped_column(
        String(30),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "stock_code",
            name="uq_user_stock",
        ),
    )


class UserIndustry(Base):
    __tablename__ = "user_industries"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        nullable=False,
    )

    industry_code: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("industries.industry_code"),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "industry_code",
            name="uq_user_industry",
        ),
    )


class NewsArticle(Base):
    __tablename__ = "news_articles"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    source: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    news_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
    )

    news_code: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    title: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    body: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    press_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )


class NewsStockMapping(Base):
    __tablename__ = "news_stock_mappings"

    news_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("news_articles.id"),
        primary_key=True,
    )

    stock_code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stocks.stock_code"),
        primary_key=True,
    )


class NewsIndustryMapping(Base):
    __tablename__ = "news_industry_mappings"

    news_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("news_articles.id"),
        primary_key=True,
    )

    industry_code: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("industries.industry_code"),
        primary_key=True,
    )


class StockNewsSummary(Base):
    __tablename__ = "stock_news_summaries"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    title: Mapped[str] = mapped_column(
        String(500),
        nullable=False,
    )

    summary_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    stock_id: Mapped[int] = mapped_column(
        nullable=False,
    )

    news_published_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "ix_news_summary_stock_published",
            "stock_id",
            "news_published_at",
        ),
    )


class StockScript(Base):
    __tablename__ = "stock_scripts"

    id: Mapped[int] = mapped_column(
        primary_key=True,
        autoincrement=True,
    )

    stock_id: Mapped[int] = mapped_column(
        nullable=False,
    )

    start_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    end_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    script_content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "stock_id",
            "start_at",
            "end_at",
            name="uq_stock_script_period",
        ),
    )
