from __future__ import annotations

import asyncio
import base64
from dataclasses import dataclass

import httpx

from tts_app.characters import voice_for
from tts_app.config import get_settings
from tts_app.script.models import DialogueLine

API_URL = "https://api.typecast.ai/v1/text-to-speech/with-timestamps"

# NOTE: Typecast가 짧은 시간에 몰리는 요청에 429를 돌려주므로, 동시 요청 수를 제한하고
# 그래도 걸리면 지수 백오프로 재시도한다.
MAX_CONCURRENT_REQUESTS = 2
MAX_RETRIES = 4
INITIAL_BACKOFF_SEC = 1.0

_semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)


@dataclass
class WordTiming:
    text: str
    start_sec: float
    end_sec: float


@dataclass
class LineAudio:
    line: DialogueLine
    audio: bytes
    audio_format: str
    words: list[WordTiming]


async def _post_with_retry(client: httpx.AsyncClient, payload: dict) -> httpx.Response:
    settings = get_settings()
    backoff = INITIAL_BACKOFF_SEC

    for attempt in range(MAX_RETRIES):
        async with _semaphore:
            response = await client.post(
                API_URL, headers={"X-API-KEY": settings.api_key}, json=payload
            )

        if response.status_code != 429:
            response.raise_for_status()
            return response

        if attempt == MAX_RETRIES - 1:
            response.raise_for_status()

        await asyncio.sleep(backoff)
        backoff *= 2

    raise AssertionError("unreachable")


async def _synthesize_line(client: httpx.AsyncClient, line: DialogueLine) -> LineAudio:
    response = await _post_with_retry(
        client,
        {
            "voice_id": voice_for(line.speaker),
            "text": line.text,
            "model": "ssfm-v30",
            "language": "kor",
            "output": {"audio_format": "mp3"},
        },
    )
    body = response.json()

    return LineAudio(
        line=line,
        audio=base64.b64decode(body["audio"]),
        audio_format=body["audio_format"],
        words=[
            WordTiming(text=w["text"], start_sec=w["start"], end_sec=w["end"])
            for w in body["words"]
        ],
    )


async def synthesize_lines(lines: list[DialogueLine]) -> list[LineAudio]:
    """대사들을 동시 요청 수를 제한하며 병렬로 합성한다."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        tasks = [_synthesize_line(client, line) for line in lines]
        return await asyncio.gather(*tasks)
