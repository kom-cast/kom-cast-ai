from __future__ import annotations

import io
from dataclasses import dataclass

from pydub import AudioSegment

from tts_app.tts.synthesizer import LineAudio

GAP_BETWEEN_LINES_MS = 400


@dataclass
class SegmentManifest:
    speaker: str
    text: str
    start_sec: float
    words: list[dict]


@dataclass
class BriefingManifest:
    duration_sec: float
    segments: list[SegmentManifest]


def merge(line_audios: list[LineAudio]) -> tuple[AudioSegment, BriefingManifest]:
    """라인 오디오를 대사 순서대로 이어붙이고, 라인-상대 타임스탬프를 전역 타임스탬프로 변환한다."""
    combined = AudioSegment.empty()
    gap = AudioSegment.silent(duration=GAP_BETWEEN_LINES_MS)
    segments: list[SegmentManifest] = []

    for i, item in enumerate(line_audios):
        clip = AudioSegment.from_file(io.BytesIO(item.audio), format=item.audio_format)
        offset_sec = combined.duration_seconds

        segments.append(
            SegmentManifest(
                speaker=item.line.speaker,
                text=item.line.text,
                start_sec=offset_sec,
                words=[
                    {
                        "text": w.text,
                        "startSec": offset_sec + w.start_sec,
                        "endSec": offset_sec + w.end_sec,
                    }
                    for w in item.words
                ],
            )
        )

        combined += clip
        if i < len(line_audios) - 1:
            combined += gap

    return combined, BriefingManifest(
        duration_sec=combined.duration_seconds, segments=segments
    )
