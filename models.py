from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class News(Base):
    __tablename__ = "news"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # 추후 시간 필터링에 사용
    published_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    summary: Mapped["NewsSummary | None"] = relationship(
        back_populates="news",
        uselist=False,
        cascade="all, delete-orphan",
    )


class NewsSummary(Base):
    __tablename__ = "news_summary"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    # 뉴스 하나당 요약 하나만 저장
    news_id: Mapped[int] = mapped_column(
        ForeignKey("news.id"),
        nullable=False,
        unique=True,
    )

    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )

    news: Mapped[News] = relationship(back_populates="summary")


class Script(Base):
    __tablename__ = "script"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=datetime.now,
    )
