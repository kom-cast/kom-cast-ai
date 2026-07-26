# app/dependencies.py

from sqlalchemy.orm import Session

from script_app.ai_client import create_openai_client
from script_app.database import SessionFactory
from script_app.repositories import (
    NewsRepository,
    ScriptRepository,
)
from script_app.services import ScriptService


def get_session():
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


def create_script_service(
    session: Session,
) -> ScriptService:
    return ScriptService(
        news_repository=NewsRepository(session),
        script_repository=ScriptRepository(session),
        ai_client=create_openai_client(),
    )
