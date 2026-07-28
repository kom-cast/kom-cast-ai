from fastapi.testclient import TestClient
from pydub.generators import Sine

import tts_app.api.briefings as briefings_module
from tts_app.main import app
from tts_app.script.models import DialogueLine
from tts_app.tts.synthesizer import LineAudio, WordTiming


def _fake_line_audio(speaker: str, text: str, seconds: float = 0.5) -> LineAudio:
    tone = Sine(440).to_audio_segment(duration=int(seconds * 1000))
    buffer = tone.export(format="mp3")
    return LineAudio(
        line=DialogueLine(speaker=speaker, text=text),
        audio=buffer.read(),
        audio_format="mp3",
        words=[WordTiming(text=text, start_sec=0.0, end_sec=seconds)],
    )


def test_repeated_script_uses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(briefings_module, "AUDIO_DIR", tmp_path)

    call_count = 0

    async def fake_synthesize_lines(lines: list[DialogueLine]) -> list[LineAudio]:
        nonlocal call_count
        call_count += 1
        return [_fake_line_audio(line.speaker, line.text) for line in lines]

    monkeypatch.setattr(briefings_module, "synthesize_lines", fake_synthesize_lines)

    client = TestClient(app)
    payload = {
        "script_id": "test",
        "target": {"type": "STOCK", "stock_id": 5930},
        "lines": [{"speaker": "코스", "text": "안녕하세요"}],
    }

    first = client.post("/briefings", json=payload)
    second = client.post("/briefings", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json()
    assert call_count == 1


def test_different_script_bypasses_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(briefings_module, "AUDIO_DIR", tmp_path)

    call_count = 0

    async def fake_synthesize_lines(lines: list[DialogueLine]) -> list[LineAudio]:
        nonlocal call_count
        call_count += 1
        return [_fake_line_audio(line.speaker, line.text) for line in lines]

    monkeypatch.setattr(briefings_module, "synthesize_lines", fake_synthesize_lines)

    client = TestClient(app)
    first = client.post(
        "/briefings",
        json={
            "script_id": "same-id",
            "target": {"type": "STOCK", "stock_id": 5930},
            "lines": [{"speaker": "코스", "text": "첫 번째 스크립트"}],
        },
    )
    second = client.post(
        "/briefings",
        json={
            "script_id": "same-id",
            "target": {"type": "STOCK", "stock_id": 5930},
            "lines": [{"speaker": "코스", "text": "다른 스크립트"}],
        },
    )

    assert first.json()["audioUrl"] != second.json()["audioUrl"]
    assert call_count == 2


def test_industry_target_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(briefings_module, "AUDIO_DIR", tmp_path)

    async def fake_synthesize_lines(lines: list[DialogueLine]) -> list[LineAudio]:
        return [_fake_line_audio(line.speaker, line.text) for line in lines]

    monkeypatch.setattr(briefings_module, "synthesize_lines", fake_synthesize_lines)

    client = TestClient(app)
    response = client.post(
        "/briefings",
        json={
            "script_id": "industry-test",
            "target": {"type": "INDUSTRY", "industry_id": 7},
            "lines": [{"speaker": "코스", "text": "반도체 업종 브리핑입니다"}],
        },
    )

    assert response.status_code == 200


def test_user_target_needs_no_id(tmp_path, monkeypatch):
    monkeypatch.setattr(briefings_module, "AUDIO_DIR", tmp_path)

    async def fake_synthesize_lines(lines: list[DialogueLine]) -> list[LineAudio]:
        return [_fake_line_audio(line.speaker, line.text) for line in lines]

    monkeypatch.setattr(briefings_module, "synthesize_lines", fake_synthesize_lines)

    client = TestClient(app)
    response = client.post(
        "/briefings",
        json={
            "script_id": "user-test",
            "target": {"type": "USER"},
            "lines": [{"speaker": "코스", "text": "사용자 브리핑입니다"}],
        },
    )

    assert response.status_code == 200


def test_stock_target_requires_stock_id(tmp_path, monkeypatch):
    monkeypatch.setattr(briefings_module, "AUDIO_DIR", tmp_path)

    client = TestClient(app)
    response = client.post(
        "/briefings",
        json={
            "script_id": "invalid-stock-test",
            "target": {"type": "STOCK"},
            "lines": [{"speaker": "코스", "text": "종목 아이디 누락"}],
        },
    )

    assert response.status_code == 422
