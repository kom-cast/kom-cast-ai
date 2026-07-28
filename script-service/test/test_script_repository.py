from datetime import datetime, timezone
from uuid import UUID

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from script_app.database import Base
from script_app.models import (
    Section,
    SectionLine,
    SectionTargetType,
    SectionType,
    Script,
    ScriptStatus,
)
from script_app.repositories import ScriptRepository


USER_ID_1 = UUID("3ad697a8-8d7d-4f80-a66f-04d994a89611")
USER_ID_2 = UUID("852471a5-f181-47f9-b526-079eef611ed8")
PERIOD_START = datetime(2026, 7, 22, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 23, tzinfo=timezone.utc)


@pytest.fixture
def session() -> Session:
    test_engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=test_engine)
    test_session_factory = sessionmaker(
        bind=test_engine,
        autoflush=False,
        expire_on_commit=False,
    )

    with test_session_factory() as test_session:
        yield test_session

    Base.metadata.drop_all(bind=test_engine)


def add_personal_section(
    session: Session,
    section_type: SectionType,
) -> Section:
    section = Section(
        section_type=section_type,
        target_type=SectionTargetType.USER,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )
    session.add(section)
    session.flush()
    return section


def add_script(
    session: Session,
    *,
    user_id: UUID,
    status: ScriptStatus,
) -> Script:
    script = Script(
        user_id=user_id,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        status=status,
    )
    session.add(script)
    session.commit()
    return script


def test_find_completed_scripts_for_users(session: Session) -> None:
    completed = add_script(
        session,
        user_id=USER_ID_1,
        status=ScriptStatus.COMPLETED,
    )
    add_script(
        session,
        user_id=USER_ID_2,
        status=ScriptStatus.FAILED,
    )
    repository = ScriptRepository(session)

    result = repository.find_completed_scripts(
        [USER_ID_1, USER_ID_2],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result == {USER_ID_1: completed}


def test_create_document_add_sections_and_complete(
    session: Session,
) -> None:
    repository = ScriptRepository(session)
    opening = add_personal_section(session, SectionType.OPENING)
    closing = add_personal_section(session, SectionType.CLOSING)

    script = repository.create_generating_script(
        USER_ID_1,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )
    links = repository.add_sections(
        script,
        [opening, closing],
    )
    repository.update_status(
        script,
        ScriptStatus.COMPLETED,
    )

    assert script.status == ScriptStatus.COMPLETED
    assert [link.section_order for link in links] == [1, 2]
    assert [link.section_type for link in links] == [
        SectionType.OPENING,
        SectionType.CLOSING,
    ]


def test_find_sections_returns_playback_order(
    session: Session,
) -> None:
    repository = ScriptRepository(session)
    opening = add_personal_section(session, SectionType.OPENING)
    closing = add_personal_section(session, SectionType.CLOSING)
    script = repository.create_generating_script(
        USER_ID_1,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )
    repository.add_sections(script, [opening, closing])

    result = repository.find_sections(script.id)

    assert [item.section_id for item in result] == [
        opening.id,
        closing.id,
    ]


def test_get_script_text_returns_lines_in_playback_order(
    session: Session,
) -> None:
    repository = ScriptRepository(session)
    opening = add_personal_section(session, SectionType.OPENING)
    closing = add_personal_section(session, SectionType.CLOSING)
    session.add_all(
        [
            SectionLine(
                section_id=opening.id,
                line_order=2,
                talker="코미",
                content="주요 소식을 전해드리겠습니다.",
            ),
            SectionLine(
                section_id=opening.id,
                line_order=1,
                talker="코스",
                content="좋은 아침입니다.",
            ),
            SectionLine(
                section_id=closing.id,
                line_order=1,
                talker="코스",
                content="편안한 아침 보내시기 바랍니다.",
            ),
        ]
    )
    script = repository.create_generating_script(
        USER_ID_1,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )
    repository.add_sections(script, [opening, closing])

    assert repository.get_script_text(script.id) == (
        "코스: 좋은 아침입니다.\n"
        "코미: 주요 소식을 전해드리겠습니다.\n"
        "코스: 편안한 아침 보내시기 바랍니다."
    )


def test_completed_document_lookup_handles_empty_input(
    session: Session,
) -> None:
    repository = ScriptRepository(session)

    result = repository.find_completed_scripts(
        [],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result == {}


def test_find_scripts_returns_all_statuses(
    session: Session,
) -> None:
    generating = add_script(
        session,
        user_id=USER_ID_1,
        status=ScriptStatus.GENERATING,
    )
    failed = add_script(
        session,
        user_id=USER_ID_2,
        status=ScriptStatus.FAILED,
    )
    repository = ScriptRepository(session)

    result = repository.find_scripts(
        [USER_ID_1, USER_ID_2],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result == {
        USER_ID_1: generating,
        USER_ID_2: failed,
    }


def test_retry_failed_script_clears_personal_sections(
    session: Session,
) -> None:
    repository = ScriptRepository(session)
    script = add_script(
        session,
        user_id=USER_ID_1,
        status=ScriptStatus.FAILED,
    )
    opening = add_personal_section(session, SectionType.OPENING)
    repository.add_sections(script, [opening])
    session.commit()
    opening_id = opening.id

    result = repository.retry_failed_script(script)

    assert result.status == ScriptStatus.GENERATING
    assert repository.find_sections(script.id) == []
    assert session.get(Section, opening_id) is None
