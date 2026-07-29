from fastapi.testclient import TestClient
from pydub.generators import Sine

import tts_app.api.briefings as briefings_module
from tts_app.main import app
from tts_app.script.models import DialogueLine
from tts_app.tts.synthesizer import LineAudio, WordTiming

# AUDIO_BACKEND=db(tts-service/.env)일 때 audios.user_id가 not null이라
# 모든 페이로드에 필요하다.
_USER_ID = "11111111-1111-1111-1111-111111111111"


def _fake_line_audio(speaker: str, text: str, seconds: float = 0.5) -> LineAudio:
    tone = Sine(440).to_audio_segment(duration=int(seconds * 1000))
    buffer = tone.export(format="mp3")
    return LineAudio(
        line=DialogueLine(speaker=speaker, text=text),
        audio=buffer.read(),
        audio_format="mp3",
        words=[WordTiming(text=text, start_sec=0.0, end_sec=seconds)],
        audio_duration=seconds,
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
        "script_id": "33333333-3333-3333-3333-333333333333",
        "user_id": _USER_ID,
        "sections": [
            {
                "target": {"type": "STOCK", "stock_code": "005930"},
                "lines": [{"speaker": "코스", "text": "안녕하세요"}],
            }
        ],
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
            "script_id": "22222222-2222-2222-2222-222222222222",
            "user_id": _USER_ID,
            "sections": [
                {
                    "target": {"type": "STOCK", "stock_code": "005930"},
                    "lines": [{"speaker": "코스", "text": "첫 번째 스크립트"}],
                }
            ],
        },
    )
    second = client.post(
        "/briefings",
        json={
            "script_id": "22222222-2222-2222-2222-222222222222",
            "user_id": _USER_ID,
            "sections": [
                {
                    "target": {"type": "STOCK", "stock_code": "005930"},
                    "lines": [{"speaker": "코스", "text": "다른 스크립트"}],
                }
            ],
        },
    )

    assert first.json()["audioUrl"] != second.json()["audioUrl"]
    assert call_count == 2


def test_response_repeats_target_on_every_segment(tmp_path, monkeypatch):
    monkeypatch.setattr(briefings_module, "AUDIO_DIR", tmp_path)

    async def fake_synthesize_lines(lines: list[DialogueLine]) -> list[LineAudio]:
        return [_fake_line_audio(line.speaker, line.text) for line in lines]

    monkeypatch.setattr(briefings_module, "synthesize_lines", fake_synthesize_lines)

    client = TestClient(app)
    response = client.post(
        "/briefings",
        json={
            "script_id": "44444444-4444-4444-4444-444444444444",
            "user_id": _USER_ID,
            "sections": [
                {
                    "target": {"type": "STOCK", "stock_code": "005930"},
                    "lines": [
                        {"speaker": "코스", "text": "오늘 삼성전자 주가는..."},
                        {"speaker": "코미", "text": "네, 외국인 매수세가 강했네요."},
                    ],
                }
            ],
        },
    )

    assert response.status_code == 200
    segments = response.json()["segments"]
    assert len(segments) == 2
    for segment in segments:
        assert segment["target"] == {"type": "STOCK", "stock_code": "005930"}


def test_each_segment_gets_its_own_section_target(tmp_path, monkeypatch):
    monkeypatch.setattr(briefings_module, "AUDIO_DIR", tmp_path)

    async def fake_synthesize_lines(lines: list[DialogueLine]) -> list[LineAudio]:
        return [_fake_line_audio(line.speaker, line.text) for line in lines]

    monkeypatch.setattr(briefings_module, "synthesize_lines", fake_synthesize_lines)

    client = TestClient(app)
    response = client.post(
        "/briefings",
        json={
            "script_id": "55555555-5555-5555-5555-555555555555",
            "user_id": _USER_ID,
            "sections": [
                {
                    "target": {"type": "STOCK", "stock_code": "005930"},
                    "lines": [
                        {"speaker": "코스", "text": "오늘 삼성전자 주가는..."},
                        {"speaker": "코미", "text": "네, 외국인 매수세가 강했네요."},
                    ],
                },
                {
                    "target": {"type": "INDUSTRY", "industry_code": "IT"},
                    "lines": [{"speaker": "코스", "text": "반도체 업종 브리핑입니다"}],
                },
                {
                    "target": {"type": "USER"},
                    "lines": [{"speaker": "코미", "text": "오늘 브리핑은 여기까지입니다"}],
                },
            ],
        },
    )

    assert response.status_code == 200
    segments = response.json()["segments"]
    assert len(segments) == 4
    assert segments[0]["target"] == {"type": "STOCK", "stock_code": "005930"}
    assert segments[1]["target"] == {"type": "STOCK", "stock_code": "005930"}
    assert segments[2]["target"] == {"type": "INDUSTRY", "industry_code": "IT"}
    assert segments[3]["target"] == {"type": "USER"}


def test_industry_target_accepted(tmp_path, monkeypatch):
    monkeypatch.setattr(briefings_module, "AUDIO_DIR", tmp_path)

    async def fake_synthesize_lines(lines: list[DialogueLine]) -> list[LineAudio]:
        return [_fake_line_audio(line.speaker, line.text) for line in lines]

    monkeypatch.setattr(briefings_module, "synthesize_lines", fake_synthesize_lines)

    client = TestClient(app)
    response = client.post(
        "/briefings",
        json={
            "script_id": "66666666-6666-6666-6666-666666666666",
            "user_id": _USER_ID,
            "sections": [
                {
                    "target": {"type": "INDUSTRY", "industry_code": "IT"},
                    "lines": [{"speaker": "코스", "text": "반도체 업종 브리핑입니다"}],
                }
            ],
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
            "script_id": "77777777-7777-7777-7777-777777777777",
            "user_id": _USER_ID,
            "sections": [
                {
                    "target": {"type": "USER"},
                    "lines": [{"speaker": "코스", "text": "사용자 브리핑입니다"}],
                }
            ],
        },
    )

    assert response.status_code == 200


def test_stock_target_requires_stock_code(tmp_path, monkeypatch):
    monkeypatch.setattr(briefings_module, "AUDIO_DIR", tmp_path)

    client = TestClient(app)
    response = client.post(
        "/briefings",
        json={
            "script_id": "invalid-stock-test",
            "sections": [
                {
                    "target": {"type": "STOCK"},
                    "lines": [{"speaker": "코스", "text": "종목 코드 누락"}],
                }
            ],
        },
    )

    assert response.status_code == 422


def test_empty_sections_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(briefings_module, "AUDIO_DIR", tmp_path)

    client = TestClient(app)
    response = client.post(
        "/briefings",
        json={"script_id": "empty-sections-test", "sections": []},
    )

    assert response.status_code == 422
