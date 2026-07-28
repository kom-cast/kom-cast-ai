from __future__ import annotations

import asyncio
import hashlib
import io
import json
from pathlib import Path

from fastapi import APIRouter

from tts_app.audio.mixer import BriefingManifest, merge
from tts_app.audio.storage import get_audio_storage
from tts_app.script.models import Script
from tts_app.tts.synthesizer import LineAudio, synthesize_lines

router = APIRouter(prefix="/briefings", tags=["briefings"])

# 로컬 백엔드(AUDIO_BACKEND=local, 기본값)에서만 쓰인다. 배포 환경은 AUDIO_BACKEND=ncp로
# 네이버클라우드 Object Storage에 저장한다. tts_app/audio/storage.py 참고.
AUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "audio"


def _cache_key(script: Script) -> str:
    """대사 내용 기반 해시. 같은 스크립트는 항상 같은 캐시를 맞고, 스크립트가
    바뀌면(예: 포트폴리오 변경) script_id가 같아도 자동으로 새로 합성된다."""
    payload = json.dumps(
        [
            line.model_dump()
            for section in script.sections
            for line in section.lines
        ],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


def _mix_and_export(line_audios: list[LineAudio]) -> tuple[bytes, BriefingManifest]:
    combined, manifest = merge(line_audios)
    buffer = io.BytesIO()
    combined.export(buffer, format="mp3")
    return buffer.getvalue(), manifest


@router.post("")
async def create_briefing(script: Script) -> dict:
    storage = get_audio_storage(AUDIO_DIR)
    cache_key = _cache_key(script)

    cached = storage.read_manifest(cache_key)
    if cached is not None:
        return cached

    lines = [line for section in script.sections for line in section.lines]
    # 섹션마다 target이 다를 수 있으므로(예: STOCK 섹션 다음 INDUSTRY 섹션), 라인
    # 순서에 맞춰 어느 섹션 소속인지 target을 함께 펼쳐 둔다.
    line_targets = [
        section.target.model_dump()
        for section in script.sections
        for _ in section.lines
    ]

    line_audios = await synthesize_lines(lines)
    # merge()/.export()는 동기 CPU/IO 작업(pydub)이라, 한 프로세스에서 다른 요청의
    # 이벤트루프를 막지 않도록 스레드풀에서 실행한다.
    audio_bytes, manifest = await asyncio.to_thread(_mix_and_export, line_audios)

    response = {
        "durationSec": manifest.duration_sec,
        "segments": [
            {
                "speaker": s.speaker,
                "target": target,
                "text": s.text,
                "startSec": s.start_sec,
                "words": s.words,
            }
            for s, target in zip(manifest.segments, line_targets)
        ],
    }
    audio_url = await asyncio.to_thread(storage.save, cache_key, audio_bytes, response)
    response["audioUrl"] = audio_url
    return response
