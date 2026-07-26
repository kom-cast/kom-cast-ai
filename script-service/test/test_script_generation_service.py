from datetime import datetime, timezone
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from script_app.ai_client import AiResponseInvalidError
from script_app.models import (
    Section,
    SectionTargetType,
    SectionType,
    ScriptDocument,
    ScriptDocumentStatus,
)
from script_app.repositories import (
    ScriptDocumentRepository,
    UserInterestRepository,
    UserInterestTargets,
)
from script_app.schemas import ScriptFailureCode
from script_app.services import (
    CommonSectionResult,
    CommonSectionService,
    PersonalSectionResult,
    PersonalSectionService,
    ScriptGenerationService,
)


USER_ID_1 = UUID("3ad697a8-8d7d-4f80-a66f-04d994a89611")
USER_ID_2 = UUID("852471a5-f181-47f9-b526-079eef611ed8")
PERIOD_START = datetime(2026, 7, 22, tzinfo=timezone.utc)
PERIOD_END = datetime(2026, 7, 23, tzinfo=timezone.utc)


def section(
    section_id: int,
    section_type: SectionType,
    target_code: str | None = None,
) -> Section:
    is_stock = section_type == SectionType.STOCK
    is_industry = section_type == SectionType.INDUSTRY
    return Section(
        id=UUID(int=section_id),
        section_type=section_type,
        target_type=(
            SectionTargetType.STOCK
            if is_stock
            else (
                SectionTargetType.INDUSTRY
                if is_industry
                else SectionTargetType.USER
            )
        ),
        stock_code=target_code if is_stock else None,
        industry_code=target_code if is_industry else None,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )


def personal_result() -> PersonalSectionResult:
    return PersonalSectionResult(
        opening=section(100, SectionType.OPENING),
        bridges=[section(101, SectionType.BRIDGE)],
        closing=section(102, SectionType.CLOSING),
    )


def create_service():
    session = Mock(spec=Session)
    interest_repository = Mock(spec=UserInterestRepository)
    document_repository = Mock(spec=ScriptDocumentRepository)
    common_service = Mock(spec=CommonSectionService)
    common_service.prepare_sections = AsyncMock()
    personal_service = Mock(spec=PersonalSectionService)
    personal_service.generate_sections = AsyncMock()
    service = ScriptGenerationService(
        session=session,
        user_interest_repository=interest_repository,
        script_document_repository=document_repository,
        common_section_service=common_service,
        personal_section_service=personal_service,
    )
    return (
        service,
        session,
        interest_repository,
        document_repository,
        common_service,
        personal_service,
    )


@pytest.mark.asyncio
async def test_reuses_completed_documents() -> None:
    (
        service,
        session,
        interest_repository,
        document_repository,
        common_service,
        personal_service,
    ) = create_service()
    existing = ScriptDocument(
        id=UUID(int=1),
        user_id=USER_ID_1,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        status=ScriptDocumentStatus.COMPLETED,
    )
    document_repository.find_documents.return_value = {
        USER_ID_1: existing
    }

    result = await service.generate(
        [USER_ID_1],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result.scripts[0].script_id == existing.id
    assert result.scripts[0].reused is True
    interest_repository.find_by_user_ids.assert_not_called()
    common_service.prepare_sections.assert_not_awaited()
    personal_service.generate_sections.assert_not_awaited()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_generates_document_with_industries_before_stocks() -> None:
    (
        service,
        session,
        interest_repository,
        document_repository,
        common_service,
        personal_service,
    ) = create_service()
    document_repository.find_documents.return_value = {}
    interest_repository.find_by_user_ids.return_value = {
        USER_ID_1: UserInterestTargets(
            stock_codes=["005930"],
            industry_codes=["SEMI"],
        )
    }
    industry = section(1, SectionType.INDUSTRY, "SEMI")
    stock = section(2, SectionType.STOCK, "005930")
    common_service.prepare_sections.return_value = (
        CommonSectionResult(
            stock_sections={"005930": stock},
            industry_sections={"SEMI": industry},
        )
    )
    document = ScriptDocument(
        id=UUID(int=10),
        user_id=USER_ID_1,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        status=ScriptDocumentStatus.GENERATING,
    )
    document_repository.create_generating_document.return_value = (
        document
    )
    generated_personal = personal_result()
    personal_service.generate_sections.return_value = (
        generated_personal
    )

    result = await service.generate(
        [USER_ID_1],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    content_sections = (
        personal_service.generate_sections.await_args.args[0]
    )
    assert content_sections == [industry, stock]
    assert result.scripts[0].reused is False
    assert result.failures == []
    assert session.commit.call_count == 3


@pytest.mark.asyncio
async def test_reports_no_interest_and_no_news_failures() -> None:
    (
        service,
        session,
        interest_repository,
        document_repository,
        common_service,
        personal_service,
    ) = create_service()
    document_repository.find_documents.return_value = {}
    interest_repository.find_by_user_ids.return_value = {
        USER_ID_1: UserInterestTargets(),
        USER_ID_2: UserInterestTargets(
            stock_codes=["005930"]
        ),
    }
    common_service.prepare_sections.return_value = (
        CommonSectionResult(
            no_news_stock_codes={"005930"}
        )
    )

    result = await service.generate(
        [USER_ID_1, USER_ID_2],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert [failure.code for failure in result.failures] == [
        ScriptFailureCode.NO_INTEREST_TARGET,
        ScriptFailureCode.NO_NEWS_FOUND,
    ]
    personal_service.generate_sections.assert_not_awaited()
    assert session.commit.call_count == 1


@pytest.mark.asyncio
async def test_ai_failure_for_one_user_does_not_rollback_other_user(
) -> None:
    (
        service,
        session,
        interest_repository,
        document_repository,
        common_service,
        personal_service,
    ) = create_service()
    document_repository.find_documents.return_value = {}
    interest_repository.find_by_user_ids.return_value = {
        USER_ID_1: UserInterestTargets(
            stock_codes=["005930"]
        ),
        USER_ID_2: UserInterestTargets(
            stock_codes=["000660"]
        ),
    }
    stock_1 = section(1, SectionType.STOCK, "005930")
    stock_2 = section(2, SectionType.STOCK, "000660")
    common_service.prepare_sections.return_value = (
        CommonSectionResult(
            stock_sections={
                "005930": stock_1,
                "000660": stock_2,
            }
        )
    )
    documents = [
        ScriptDocument(
            id=UUID(int=10),
            user_id=USER_ID_1,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            status=ScriptDocumentStatus.GENERATING,
        ),
        ScriptDocument(
            id=UUID(int=11),
            user_id=USER_ID_2,
            period_start=PERIOD_START,
            period_end=PERIOD_END,
            status=ScriptDocumentStatus.GENERATING,
        ),
    ]
    document_repository.create_generating_document.side_effect = (
        documents
    )
    personal_service.generate_sections.side_effect = [
        AiResponseInvalidError("invalid"),
        PersonalSectionResult(
            opening=section(100, SectionType.OPENING),
            bridges=[],
            closing=section(101, SectionType.CLOSING),
        ),
    ]

    result = await service.generate(
        [USER_ID_1, USER_ID_2],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result.scripts[0].user_id == USER_ID_2
    assert result.failures[0].user_id == USER_ID_1
    assert result.failures[0].code == (
        ScriptFailureCode.AI_RESPONSE_INVALID
    )
    session.rollback.assert_called_once()
    assert session.commit.call_count == 5


@pytest.mark.asyncio
async def test_common_target_ai_failure_fails_affected_user() -> None:
    (
        service,
        session,
        interest_repository,
        document_repository,
        common_service,
        personal_service,
    ) = create_service()
    document_repository.find_documents.return_value = {}
    interest_repository.find_by_user_ids.return_value = {
        USER_ID_1: UserInterestTargets(
            stock_codes=["005930"]
        )
    }
    common_service.prepare_sections.return_value = (
        CommonSectionResult(
            failed_stock_codes={"005930"}
        )
    )

    result = await service.generate(
        [USER_ID_1],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result.failures[0].code == (
        ScriptFailureCode.AI_GENERATION_FAILED
    )
    personal_service.generate_sections.assert_not_awaited()


@pytest.mark.asyncio
async def test_existing_generating_document_is_not_duplicated() -> None:
    (
        service,
        session,
        interest_repository,
        document_repository,
        common_service,
        personal_service,
    ) = create_service()
    generating = ScriptDocument(
        id=UUID(int=10),
        user_id=USER_ID_1,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        status=ScriptDocumentStatus.GENERATING,
    )
    document_repository.find_documents.return_value = {
        USER_ID_1: generating
    }

    result = await service.generate(
        [USER_ID_1],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    assert result.failures[0].code == (
        ScriptFailureCode.GENERATION_IN_PROGRESS
    )
    interest_repository.find_by_user_ids.assert_not_called()
    common_service.prepare_sections.assert_not_awaited()
    personal_service.generate_sections.assert_not_awaited()
    session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_failed_document_is_retried_with_same_document() -> None:
    (
        service,
        session,
        interest_repository,
        document_repository,
        common_service,
        personal_service,
    ) = create_service()
    failed = ScriptDocument(
        id=UUID(int=10),
        user_id=USER_ID_1,
        period_start=PERIOD_START,
        period_end=PERIOD_END,
        status=ScriptDocumentStatus.FAILED,
    )
    document_repository.find_documents.return_value = {
        USER_ID_1: failed
    }
    interest_repository.find_by_user_ids.return_value = {
        USER_ID_1: UserInterestTargets(
            stock_codes=["005930"]
        )
    }
    stock = section(1, SectionType.STOCK, "005930")
    common_service.prepare_sections.return_value = (
        CommonSectionResult(
            stock_sections={"005930": stock}
        )
    )
    document_repository.retry_failed_document.return_value = failed
    personal_service.generate_sections.return_value = (
        PersonalSectionResult(
            opening=section(100, SectionType.OPENING),
            bridges=[],
            closing=section(101, SectionType.CLOSING),
        )
    )

    result = await service.generate(
        [USER_ID_1],
        period_start=PERIOD_START,
        period_end=PERIOD_END,
    )

    document_repository.retry_failed_document.assert_called_once_with(
        failed
    )
    (
        document_repository
        .create_generating_document
        .assert_not_called()
    )
    assert result.scripts[0].script_id == failed.id
    assert result.scripts[0].reused is False
