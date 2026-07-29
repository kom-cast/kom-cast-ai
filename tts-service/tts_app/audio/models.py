from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    JSON,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    Numeric,
    String,
    Text,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from tts_app.audio.db import Base


class AudioBinary(Base):
    """Object Storage 장애 기간 동안 MP3 바이너리를 임시로 담아두는 테이블.
    백엔드(Spring Boot)가 이 테이블을 직접 조회해 오디오를 스트리밍한다."""

    __tablename__ = "audio_binaries"

    id: Mapped[UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid4,
    )

    data: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class Audio(Base):
    """Spring이 소유한 audios 테이블. AUDIO_BACKEND=db일 때는 Spring을 거치지
    않고 tts-service가 이 테이블에 직접 부모 레코드를 만든다(schema는
    dbdiagram ERD 기준, 이미 Spring 쪽 마이그레이션으로 존재하는 테이블이라
    create_tables()는 이 테이블을 새로 만들지 않는다)."""

    __tablename__ = "audios"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    script_id: Mapped[UUID | None] = mapped_column(Uuid, nullable=True)
    audio_type: Mapped[str] = mapped_column(String(30), nullable=False)
    audio_url: Mapped[str] = mapped_column(Text, nullable=False)
    duration_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
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


class AudioSegment(Base):
    """Spring이 소유한 audio_segments 테이블. stock_code는 STOCK 타겟
    세그먼트에서만 채우고, 그 외(INDUSTRY/USER)는 null로 둔다 — Spring 쪽의
    stock_code 매핑 버그(FK 위반)를 tts-service에서 원천적으로 피하기 위함."""

    __tablename__ = "audio_segments"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    audio_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("audios.id"), nullable=False
    )
    segment_order: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(50), nullable=False)
    stock_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_sec: Mapped[float] = mapped_column(Numeric, nullable=False)
    words: Mapped[list | None] = mapped_column(JSON, nullable=True)
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
