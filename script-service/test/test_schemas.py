from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from script_app.schemas import (
    GenerateUserScriptsRequest,
    GenerateUserScriptsResponse,
    GeneratedScriptResult,
    ScriptFailureCode,
    ScriptFailureResult,
)


USER_ID_1 = UUID("3ad697a8-8d7d-4f80-a66f-04d994a89611")
USER_ID_2 = UUID("852471a5-f181-47f9-b526-079eef611ed8")


def valid_period() -> tuple[datetime, datetime]:
    start_at = datetime(2026, 7, 22, tzinfo=timezone(timedelta(hours=9)))
    end_at = datetime(2026, 7, 23, tzinfo=timezone(timedelta(hours=9)))
    return start_at, end_at


def test_generate_user_scripts_request_accepts_valid_input() -> None:
    start_at, end_at = valid_period()

    request = GenerateUserScriptsRequest(
        start_at=start_at,
        end_at=end_at,
        user_ids=[USER_ID_1, USER_ID_2],
    )

    assert request.start_at == start_at
    assert request.end_at == end_at
    assert request.user_ids == [USER_ID_1, USER_ID_2]


def test_generate_user_scripts_request_removes_duplicate_users() -> None:
    start_at, end_at = valid_period()

    request = GenerateUserScriptsRequest(
        start_at=start_at,
        end_at=end_at,
        user_ids=[USER_ID_1, USER_ID_2, USER_ID_1],
    )

    assert request.user_ids == [USER_ID_1, USER_ID_2]


@pytest.mark.parametrize("field_name", ["start_at", "end_at"])
def test_generate_user_scripts_request_requires_timezone(
    field_name: str,
) -> None:
    start_at, end_at = valid_period()
    values = {
        "start_at": start_at,
        "end_at": end_at,
        "user_ids": [USER_ID_1],
    }
    values[field_name] = values[field_name].replace(tzinfo=None)

    with pytest.raises(
        ValidationError,
        match="timezone information is required",
    ):
        GenerateUserScriptsRequest(**values)


@pytest.mark.parametrize(
    ("start_at", "end_at"),
    [
        (
            datetime(2026, 7, 22, tzinfo=timezone.utc),
            datetime(2026, 7, 22, tzinfo=timezone.utc),
        ),
        (
            datetime(2026, 7, 23, tzinfo=timezone.utc),
            datetime(2026, 7, 22, tzinfo=timezone.utc),
        ),
    ],
)
def test_generate_user_scripts_request_rejects_invalid_period(
    start_at: datetime,
    end_at: datetime,
) -> None:
    with pytest.raises(
        ValidationError,
        match="start_at must be earlier than end_at",
    ):
        GenerateUserScriptsRequest(
            start_at=start_at,
            end_at=end_at,
            user_ids=[USER_ID_1],
        )


def test_generate_user_scripts_request_rejects_empty_users() -> None:
    start_at, end_at = valid_period()

    with pytest.raises(ValidationError):
        GenerateUserScriptsRequest(
            start_at=start_at,
            end_at=end_at,
            user_ids=[],
        )


def test_generate_user_scripts_response_contains_success_and_failure() -> None:
    response = GenerateUserScriptsResponse(
        scripts=[
            GeneratedScriptResult(
                script_id=UUID(
                    "1ee14e43-fb5c-4225-8cb3-dc84a31e8423"
                ),
                user_id=USER_ID_1,
                reused=False,
                script_text="코스: 좋은 아침입니다.",
            )
        ],
        failures=[
            ScriptFailureResult(
                user_id=USER_ID_2,
                code=ScriptFailureCode.NO_INTEREST_TARGET,
                message="관심 종목 또는 업종이 없습니다.",
            )
        ],
    )

    assert response.scripts[0].user_id == USER_ID_1
    assert response.failures[0].code == (
        ScriptFailureCode.NO_INTEREST_TARGET
    )
