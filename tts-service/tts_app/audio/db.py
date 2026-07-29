from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from tts_app.config import get_database_settings

_settings = get_database_settings()

engine = create_engine(
    _settings.database_url,
    connect_args=(
        {"check_same_thread": False}
        if _settings.database_url.startswith("sqlite")
        else {}
    ),
)

SessionFactory = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)

Base = declarative_base()


def create_tables() -> None:
    from tts_app.audio import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
