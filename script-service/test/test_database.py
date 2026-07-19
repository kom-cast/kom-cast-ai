from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.database import DATABASE_URL, SessionFactory


def test_database_connection() -> None:
    test_engine = create_engine(
        "sqlite:///:memory:",
    )

    test_session_factory = sessionmaker(
        bind=test_engine,
    )

    with test_session_factory() as session:
        result = session.execute(
            text("SELECT 1")
        ).scalar_one()

    assert result == 1


def test_database_url_is_loaded() -> None:
    assert DATABASE_URL
    assert DATABASE_URL.startswith("sqlite")


def test_project_session_factory() -> None:
    with SessionFactory() as session:
        result = session.execute(
            text("SELECT 1")
        ).scalar_one()

    assert result == 1
