from unittest.mock import AsyncMock, Mock
from uuid import UUID

from fastapi.testclient import TestClient

from script_app.main import app
from script_app.schemas import (
    GeneratedScriptResult,
    GenerateUserScriptsResponse,
    ScriptFailureCode,
    ScriptFailureResult,
)
from script_app.services import (
    ResourceInUseError,
    ResourceNotFoundError,
)


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


def test_generate_scripts(monkeypatch) -> None:
    fake_service = Mock()
    user_id_1 = UUID(
        "3ad697a8-8d7d-4f80-a66f-04d994a89611"
    )
    user_id_2 = UUID(
        "852471a5-f181-47f9-b526-079eef611ed8"
    )

    fake_service.generate = AsyncMock(
        return_value=GenerateUserScriptsResponse(
            scripts=[
                GeneratedScriptResult(
                    script_id=UUID(
                        "1ee14e43-fb5c-4225-8cb3-dc84a31e8423"
                    ),
                    user_id=user_id_1,
                    reused=False,
                    script_text=(
                        "코스: 좋은 아침입니다.\n"
                        "코미: 주요 소식을 전해드리겠습니다."
                    ),
                )
            ],
            failures=[
                ScriptFailureResult(
                    user_id=user_id_2,
                    code=ScriptFailureCode.NO_NEWS_FOUND,
                    message="조회 기간에 관련 뉴스가 없습니다.",
                )
            ],
        )
    )

    def fake_create_script_generation_service(session):
        return fake_service

    monkeypatch.setattr(
        (
            "script_app.api.scripts."
            "create_script_generation_service"
        ),
        fake_create_script_generation_service,
    )

    response = client.post(
        "/scripts/generate",
        json={
            "start_at": "2026-07-22T00:00:00+09:00",
            "end_at": "2026-07-23T00:00:00+09:00",
            "user_ids": [str(user_id_1), str(user_id_2)],
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "scripts": [
            {
                "script_id": (
                    "1ee14e43-fb5c-4225-8cb3-dc84a31e8423"
                ),
                "user_id": str(user_id_1),
                "reused": False,
                "script_text": (
                    "코스: 좋은 아침입니다.\n"
                    "코미: 주요 소식을 전해드리겠습니다."
                ),
            }
        ],
        "failures": [
            {
                "user_id": str(user_id_2),
                "code": "NO_NEWS_FOUND",
                "message": "조회 기간에 관련 뉴스가 없습니다.",
            }
        ],
    }

    fake_service.generate.assert_awaited_once()


def test_generate_scripts_rejects_timestamp_without_timezone() -> None:
    response = client.post(
        "/scripts/generate",
        json={
            "start_at": "2026-07-22T00:00:00",
            "end_at": "2026-07-23T00:00:00",
            "user_ids": [
                "3ad697a8-8d7d-4f80-a66f-04d994a89611"
            ],
        },
    )

    assert response.status_code == 422


def test_generate_scripts_rejects_empty_users() -> None:
    response = client.post(
        "/scripts/generate",
        json={
            "start_at": "2026-07-22T00:00:00+09:00",
            "end_at": "2026-07-23T00:00:00+09:00",
            "user_ids": [],
        },
    )

    assert response.status_code == 422


def test_generate_scripts_returns_500_for_request_wide_failure(
    monkeypatch,
) -> None:
    fake_service = Mock()
    fake_service.generate = AsyncMock(
        side_effect=RuntimeError("database unavailable")
    )
    monkeypatch.setattr(
        (
            "script_app.api.scripts."
            "create_script_generation_service"
        ),
        lambda session: fake_service,
    )
    error_client = TestClient(
        app,
        raise_server_exceptions=False,
    )

    response = error_client.post(
        "/scripts/generate",
        json={
            "start_at": "2026-07-22T00:00:00+09:00",
            "end_at": "2026-07-23T00:00:00+09:00",
            "user_ids": [
                "3ad697a8-8d7d-4f80-a66f-04d994a89611"
            ],
        },
    )

    assert response.status_code == 500


def test_delete_script_returns_no_content(monkeypatch) -> None:
    script_id = UUID("1ee14e43-fb5c-4225-8cb3-dc84a31e8423")
    fake_service = Mock()
    monkeypatch.setattr(
        (
            "script_app.api.scripts."
            "create_script_deletion_service"
        ),
        lambda session: fake_service,
    )

    response = client.delete(f"/scripts/{script_id}")

    assert response.status_code == 204
    assert response.content == b""
    fake_service.delete_script.assert_called_once_with(script_id)


def test_delete_script_returns_not_found(monkeypatch) -> None:
    fake_service = Mock()
    fake_service.delete_script.side_effect = ResourceNotFoundError
    monkeypatch.setattr(
        (
            "script_app.api.scripts."
            "create_script_deletion_service"
        ),
        lambda session: fake_service,
    )

    response = client.delete(f"/scripts/{UUID(int=1)}")

    assert response.status_code == 404


def test_delete_section_returns_no_content(monkeypatch) -> None:
    section_id = UUID("2ee14e43-fb5c-4225-8cb3-dc84a31e8423")
    fake_service = Mock()
    monkeypatch.setattr(
        (
            "script_app.api.sections."
            "create_script_deletion_service"
        ),
        lambda session: fake_service,
    )

    response = client.delete(f"/sections/{section_id}")

    assert response.status_code == 204
    assert response.content == b""
    fake_service.delete_section.assert_called_once_with(section_id)


def test_delete_section_returns_conflict_when_in_use(
    monkeypatch,
) -> None:
    fake_service = Mock()
    fake_service.delete_section.side_effect = ResourceInUseError
    monkeypatch.setattr(
        (
            "script_app.api.sections."
            "create_script_deletion_service"
        ),
        lambda session: fake_service,
    )

    response = client.delete(f"/sections/{UUID(int=1)}")

    assert response.status_code == 409
