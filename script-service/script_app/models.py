from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    text,
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
        unique=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
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

    is_kospi200: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
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

    summary: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    press_code: Mapped[int | None] = mapped_column(
        Integer,
        nullable=True,
    )


class NewsStockMapping(Base):
    __tablename__ = "news_stock"

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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class NewsIndustryMapping(Base):
    __tablename__ = "news_industry"

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

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class MarketPrice(Base):
    __tablename__ = "market_prices"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    stock_code: Mapped[str] = mapped_column(
        String(20),
        ForeignKey("stocks.stock_code"),
        nullable=False,
    )

    traded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    interval: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    open_price: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    high_price: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    low_price: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    close_price: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    volume: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    change_rate: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    trading_value: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    market_cap: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    vwap: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    provider: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    raw_external_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "stock_code",
            "traded_at",
            "interval",
            "provider",
            name="uq_market_price_source",
        ),
    )


class IndustryPrice(Base):
    __tablename__ = "industry_prices"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    industry_code: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("industries.industry_code"),
        nullable=False,
    )

    traded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    index_value: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    change_amount: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    change_rate: Mapped[Decimal] = mapped_column(
        Numeric,
        nullable=False,
    )

    open_value: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    high_value: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    low_value: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    volume: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    trading_value: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
    )

    market_cap: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    market_cap_free_float: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    shares_outstanding: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    foreign_ownership_rate: Mapped[Decimal | None] = mapped_column(
        Numeric,
        nullable=True,
    )

    short_sale_volume: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    short_sale_value: Mapped[int | None] = mapped_column(
        BigInteger,
        nullable=True,
    )

    provider: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    raw_external_id: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "industry_code",
            "traded_at",
            "provider",
            name="uq_industry_price_source",
        ),
    )


class SectionType(str, Enum):
    STOCK = "STOCK"
    INDUSTRY = "INDUSTRY"
    OPENING = "OPENING"
    BRIDGE = "BRIDGE"
    CLOSING = "CLOSING"


class SectionTargetType(str, Enum):
    STOCK = "STOCK"
    INDUSTRY = "INDUSTRY"
    USER = "USER"


class Section(Base):
    __tablename__ = "sections"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    section_type: Mapped[SectionType] = mapped_column(
        SqlEnum(
            SectionType,
            native_enum=False,
            length=30,
            validate_strings=True,
        ),
        nullable=False,
    )

    target_type: Mapped[SectionTargetType] = mapped_column(
        SqlEnum(
            SectionTargetType,
            native_enum=False,
            length=30,
            validate_strings=True,
        ),
        nullable=False,
    )

    stock_code: Mapped[str | None] = mapped_column(
        String(20),
        ForeignKey("stocks.stock_code"),
        nullable=True,
    )

    industry_code: Mapped[str | None] = mapped_column(
        String(50),
        ForeignKey("industries.industry_code"),
        nullable=True,
    )

    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        CheckConstraint(
            "("
            "section_type = 'STOCK' "
            "AND target_type = 'STOCK' "
            "AND stock_code IS NOT NULL "
            "AND industry_code IS NULL"
            ") OR ("
            "section_type = 'INDUSTRY' "
            "AND target_type = 'INDUSTRY' "
            "AND stock_code IS NULL "
            "AND industry_code IS NOT NULL"
            ") OR ("
            "section_type IN ('OPENING', 'BRIDGE', 'CLOSING') "
            "AND target_type = 'USER' "
            "AND stock_code IS NULL "
            "AND industry_code IS NULL"
            ")",
            name="ck_section_target",
        ),
        Index(
            "uq_sections_stock_reuse",
            "stock_code",
            "period_start",
            "period_end",
            unique=True,
            postgresql_where=text("section_type = 'STOCK'"),
            sqlite_where=text("section_type = 'STOCK'"),
        ),
        Index(
            "uq_sections_industry_reuse",
            "industry_code",
            "period_start",
            "period_end",
            unique=True,
            postgresql_where=text("section_type = 'INDUSTRY'"),
            sqlite_where=text("section_type = 'INDUSTRY'"),
        ),
    )


class SectionLine(Base):
    __tablename__ = "section_lines"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    section_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("sections.id", ondelete="CASCADE"),
        nullable=False,
    )

    line_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    talker: Mapped[str] = mapped_column(
        String(50),
        nullable=False,
    )

    content: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "section_id",
            "line_order",
            name="uq_section_line_order",
        ),
    )


class ScriptDocumentStatus(str, Enum):
    GENERATING = "GENERATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ScriptDocument(Base):
    __tablename__ = "script_documents"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid,
        nullable=False,
    )

    period_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    period_end: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )

    status: Mapped[ScriptDocumentStatus] = mapped_column(
        SqlEnum(
            ScriptDocumentStatus,
            native_enum=False,
            length=30,
            validate_strings=True,
        ),
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "period_start",
            "period_end",
            name="uq_script_document_user_period",
        ),
    )


class ScriptSection(Base):
    __tablename__ = "script_sections"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    document_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("script_documents.id", ondelete="CASCADE"),
        nullable=False,
    )

    section_id: Mapped[UUID] = mapped_column(
        Uuid,
        ForeignKey("sections.id"),
        nullable=False,
    )

    section_order: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    section_type: Mapped[SectionType] = mapped_column(
        SqlEnum(
            SectionType,
            native_enum=False,
            length=30,
            validate_strings=True,
        ),
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint(
            "section_order >= 1",
            name="ck_script_section_order_positive",
        ),
        UniqueConstraint(
            "document_id",
            "section_order",
            name="uq_script_section_order",
        ),
    )

