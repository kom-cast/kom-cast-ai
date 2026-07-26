from datetime import date, datetime, timezone
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
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
