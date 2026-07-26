from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from script_app.config import DATABASE_URL


engine = create_engine(
    DATABASE_URL,
    connect_args=(
        {"check_same_thread": False}
        if DATABASE_URL.startswith("sqlite")
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
    from script_app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
