from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from script_app.database import Base
from script_app.models import (
    Industry,
    Section,
    SectionTargetType,
    SectionType,
    Stock,
    Script,
    ScriptStatus,
)
from script_app.repositories import (
    ScriptRepository,
    SectionInUseError,
    SectionLineData,
    SectionRepository,
)
from uuid import UUID


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


def add_master_data(session: Session) -> None:
    session.add(
        Industry(
            industry_code="SEMI",
            industry_name="반도체",
        )
    )
    session.add(
        Stock(
            stock_code="005930",
            corp_code="00126380",
            corp_name="삼성전자",
            industry_code="SEMI",
        )
    )
    session.commit()


def create_section(
    *,
    section_type: SectionType,
    stock_code: str | None = None,
    industry_code: str | None = None,
) -> Section:
    target_type = (
        SectionTargetType.STOCK
        if section_type == SectionType.STOCK
        else SectionTargetType.INDUSTRY
    )
    return Section(
        section_type=section_type,
        target_type=target_type,
        stock_code=stock_code,
        industry_code=industry_code,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )


def test_save_section_with_ordered_lines(session: Session) -> None:
    add_master_data(session)
    repository = SectionRepository(session)

    section = repository.save_with_lines(
        create_section(
            section_type=SectionType.STOCK,
            stock_code="005930",
        ),
        [
            SectionLineData(
                talker="코스",
                content="삼성전자 소식을 살펴보겠습니다.",
            ),
            SectionLineData(
                talker="코미",
                content="주요 뉴스부터 설명하겠습니다.",
            ),
        ],
    )

    lines = repository.find_lines_by_section_ids([section.id])

    assert section.id is not None
    assert [line.line_order for line in lines[section.id]] == [1, 2]
    assert [line.talker for line in lines[section.id]] == [
        "코스",
        "코미",
    ]


def test_common_section_conflict_reuses_existing_section(
    session: Session,
) -> None:
    add_master_data(session)
    repository = SectionRepository(session)
    existing = repository.save_common_section_with_lines_or_get(
        create_section(
            section_type=SectionType.STOCK,
            stock_code="005930",
        ),
        [
            SectionLineData(
                talker="코스",
                content="먼저 저장된 발화",
            )
        ],
    )

    result = repository.save_common_section_with_lines_or_get(
        create_section(
            section_type=SectionType.STOCK,
            stock_code="005930",
        ),
        [
            SectionLineData(
                talker="코미",
                content="나중에 생성된 발화",
            )
        ],
    )

    assert result.id == existing.id
    lines = repository.find_lines_by_section_ids([existing.id])
    assert [line.content for line in lines[existing.id]] == [
        "먼저 저장된 발화"
    ]


def test_conflict_reuse_rejects_personal_sections(
    session: Session,
) -> None:
    repository = SectionRepository(session)
    personal_section = Section(
        section_type=SectionType.OPENING,
        target_type=SectionTargetType.USER,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    with pytest.raises(
        ValueError,
        match="only common sections",
    ):
        repository.save_common_section_with_lines_or_get(
            personal_section,
            [],
        )


def test_find_reusable_stock_sections(session: Session) -> None:
    add_master_data(session)
    repository = SectionRepository(session)
    reusable = repository.save_with_lines(
        create_section(
            section_type=SectionType.STOCK,
            stock_code="005930",
        ),
        [],
    )
    result = repository.find_stock_sections(
        ["005930", "000660"],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result == {"005930": reusable}


def test_find_reusable_industry_sections(session: Session) -> None:
    add_master_data(session)
    repository = SectionRepository(session)
    reusable = repository.save_with_lines(
        create_section(
            section_type=SectionType.INDUSTRY,
            industry_code="SEMI",
        ),
        [],
    )

    result = repository.find_industry_sections(
        ["SEMI", "DISPLAY"],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result == {"SEMI": reusable}


def test_section_repository_handles_empty_inputs(
    session: Session,
) -> None:
    repository = SectionRepository(session)

    assert repository.find_stock_sections(
        [],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    ) == {}
    assert repository.find_industry_sections(
        [],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    ) == {}
    assert repository.find_lines_by_section_ids([]) == {}


def test_delete_unreferenced_section_and_lines(
    session: Session,
) -> None:
    add_master_data(session)
    repository = SectionRepository(session)
    section = repository.save_with_lines(
        create_section(
            section_type=SectionType.STOCK,
            stock_code="005930",
        ),
        [
            SectionLineData(
                talker="코스",
                content="삭제할 발화입니다.",
            )
        ],
    )

    assert repository.delete_by_id(section.id) is True
    assert session.get(Section, section.id) is None
    assert repository.find_lines_by_section_ids(
        [section.id]
    )[section.id] == []


def test_delete_section_rejects_script_reference(
    session: Session,
) -> None:
    section_repository = SectionRepository(session)
    section = Section(
        section_type=SectionType.OPENING,
        target_type=SectionTargetType.USER,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )
    section_repository.save_with_lines(section, [])
    script_repository = ScriptRepository(session)
    script = Script(
        user_id=UUID(int=1),
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        status=ScriptStatus.COMPLETED,
    )
    session.add(script)
    session.flush()
    script_repository.add_sections(script, [section])

    with pytest.raises(SectionInUseError):
        section_repository.delete_by_id(section.id)
