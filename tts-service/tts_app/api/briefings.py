from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fastapi import APIRouter

from tts_app.audio.mixer import merge
from tts_app.script.models import Script
from tts_app.tts.synthesizer import synthesize_lines

router = APIRouter(prefix="/briefings", tags=["briefings"])

# TODO: 배포 환경에서는 로컬 디스크 대신 S3/CDN 등 오브젝트 스토리지로 교체
AUDIO_DIR = Path(__file__).resolve().parent.parent.parent / "static" / "audio"


def _cache_key(script: Script) -> str:
    """대사 내용 기반 해시. 같은 스크립트는 항상 같은 캐시를 맞고, 스크립트가
    바뀌면(예: 포트폴리오 변경) briefing_id가 같아도 자동으로 새로 합성된다."""
    payload = json.dumps(
        [line.model_dump() for line in script.lines],
        ensure_ascii=False,
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode()).hexdigest()[:16]


@router.post("")
async def create_briefing(script: Script) -> dict:
    cache_key = _cache_key(script)
    audio_path = AUDIO_DIR / f"{cache_key}.mp3"
    manifest_path = AUDIO_DIR / f"{cache_key}.json"

    if audio_path.exists() and manifest_path.exists():
        return json.loads(manifest_path.read_text())

    line_audios = await synthesize_lines(script.lines)
    combined, manifest = merge(line_audios)
    combined.export(audio_path, format="mp3")

    response = {
        "audioUrl": f"/static/audio/{cache_key}.mp3",
        "durationSec": manifest.duration_sec,
        "segments": [
            {
                "speaker": s.speaker,
                "stock": s.stock,
                "text": s.text,
                "startSec": s.start_sec,
                "words": s.words,
            }
            for s in manifest.segments
        ],
    }
    manifest_path.write_text(json.dumps(response, ensure_ascii=False))
    return response
