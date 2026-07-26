from unittest.mock import AsyncMock, Mock

from fastapi.testclient import TestClient

from script_app.main import app


client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


def test_generate_scripts(monkeypatch) -> None:
    fake_service = Mock()

    fake_service.generate_scripts = AsyncMock(
        return_value={
            1: "script1",
            2: "",
            3: "script3",
        }
    )

    def fake_create_script_service(session):
        return fake_service

    monkeypatch.setattr(
        "script_app.api.scripts.create_script_service",
        fake_create_script_service,
    )

    response = client.post(
        "/scripts/generate",
        json={
            "stock_ids": [1, 2, 3],
            "start_at": "2026-07-18T00:00:00",
            "end_at": "2026-07-19T00:00:00",
        },
    )

    assert response.status_code == 200

    assert response.json() == {
        "status": "completed",
        "generated_stock_ids": [1, 3],
        "skipped_stock_ids": [2],
    }

    fake_service.generate_scripts.assert_awaited_once()
