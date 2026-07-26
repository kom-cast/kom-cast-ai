import base64
import json

import httpx
import pytest
import respx

from tts_app.script.models import DialogueLine
from tts_app.tts.synthesizer import API_URL, synthesize_lines


@pytest.fixture(autouse=True)
def _typecast_api_key(monkeypatch):
    monkeypatch.setenv("TYPECAST_API_KEY", "test-key")
    from tts_app.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _fake_response(text: str) -> dict:
    return {
        "audio": base64.b64encode(b"fake-audio-bytes").decode(),
        "audio_format": "mp3",
        "audio_duration": 1.2,
        "words": [{"text": text, "start": 0.0, "end": 1.2}],
    }


@pytest.mark.asyncio
@respx.mock
async def test_synthesize_lines_calls_typecast_per_line():
    route = respx.post(API_URL).mock(
        side_effect=lambda request: httpx.Response(
            200, json=_fake_response(json.loads(request.content)["text"])
        )
    )

    lines = [
        DialogueLine(speaker="코스", stock="삼성전자", text="코스 대사"),
        DialogueLine(speaker="코미", stock="삼성전자", text="코미 대사"),
    ]
    results = await synthesize_lines(lines)

    assert route.call_count == 2
    assert [r.line.speaker for r in results] == ["코스", "코미"]
    assert results[0].words[0].text == "코스 대사"
    assert results[0].audio == b"fake-audio-bytes"
