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
