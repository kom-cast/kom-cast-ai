from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import DateTime, LargeBinary, Uuid
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
