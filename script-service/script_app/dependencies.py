# app/dependencies.py

from sqlalchemy.orm import Session

from script_app.ai_client import create_openai_client
from script_app.database import SessionFactory
from script_app.repositories import (
    NewsRepository,
    ScriptRepository,
    ScriptDocumentRepository,
    SectionRepository,
    UserInterestRepository,
)
from script_app.services import (
    CommonSectionService,
    PersonalSectionService,
    ScriptGenerationService,
    ScriptService,
)


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


def create_script_generation_service(
    session: Session,
) -> ScriptGenerationService:
    ai_client = create_openai_client()
    news_repository = NewsRepository(session)
    section_repository = SectionRepository(session)

    return ScriptGenerationService(
        session=session,
        user_interest_repository=UserInterestRepository(session),
        script_document_repository=ScriptDocumentRepository(
            session
        ),
        common_section_service=CommonSectionService(
            news_repository=news_repository,
            section_repository=section_repository,
            ai_client=ai_client,
        ),
        personal_section_service=PersonalSectionService(
            section_repository=section_repository,
            ai_client=ai_client,
        ),
    )
