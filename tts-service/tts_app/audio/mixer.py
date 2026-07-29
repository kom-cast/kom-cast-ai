from __future__ import annotations

import io
from dataclasses import dataclass

from pydub import AudioSegment
from pydub.silence import detect_leading_silence

from tts_app.tts.synthesizer import LineAudio

GAP_BETWEEN_LINES_MS = 400

# mp3 인코더가 프레임 정렬을 위해 앞에 끼워 넣는 프라이밍 샘플(디코더가 그대로
# 무음으로 복원하는 부분) 때문에, 디코드된 clip 안에서 실제 발화가
# words[0].startSec(=0초)보다 늦게 시작할 수 있음. _match_duration은 clip
# 끝부분만 다듬기 때문에 이 앞부분 오차는 그대로 남아, 라인 길이와 무관하게
# 매 라인마다 일정한 만큼 하이라이트가 오디오보다 앞서가는 것처럼 들리게 됨.
# 정상적인 발화 사이 무음까지 잘라내지 않도록 상한을 둔다.
_LEADING_SILENCE_THRESH_DBFS = -40
_LEADING_SILENCE_CHUNK_MS = 5
_MAX_LEADING_TRIM_MS = 100


def _strip_leading_silence(clip: AudioSegment) -> AudioSegment:
    trim_ms = detect_leading_silence(
        clip,
        silence_threshold=_LEADING_SILENCE_THRESH_DBFS,
        chunk_size=_LEADING_SILENCE_CHUNK_MS,
    )
    trim_ms = min(trim_ms, _MAX_LEADING_TRIM_MS)
    return clip[trim_ms:] if trim_ms else clip


def _match_duration(clip: AudioSegment, target_sec: float) -> AudioSegment:
    """mp3 인코딩/디코딩 왕복(인코더 프라이밍 샘플, 프레임 양자화 등) 때문에
    ffmpeg로 디코딩한 clip 길이가 Typecast가 words[].start/end 계산에 쓴
    "진짜" 길이(audio_duration)와 라인마다 미세하게 어긋날 수 있음. 이 오차를
    안 잡고 그대로 다음 라인의 offset(=combined.duration_seconds)에 누적시키면
    재생 중반부로 갈수록 하이라이트가 오디오보다 점점 앞서가는 문제가 생김.
    그래서 최종 합본 오디오에 실제로 들어가는 clip 길이 자체를 audio_duration에
    맞춰 자르거나 무음으로 채워, offset 계산 기준과 실제 오디오 길이를 일치시킴.
    """
    target_ms = round(target_sec * 1000)
    diff_ms = target_ms - len(clip)
    if diff_ms > 0:
        return clip + AudioSegment.silent(
            duration=diff_ms, frame_rate=clip.frame_rate
        )
    if diff_ms < 0:
        return clip[:target_ms]
    return clip


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
    combined: AudioSegment | None = None
    segments: list[SegmentManifest] = []

    for i, item in enumerate(line_audios):
        clip = AudioSegment.from_file(io.BytesIO(item.audio), format=item.audio_format)
        clip = _strip_leading_silence(clip)
        clip = _match_duration(clip, item.audio_duration)

        # NOTE: AudioSegment.empty()는 기본 포맷(frame_rate 등)이 실제 TTS
        # 오디오와 달라서, += 할 때마다 pydub이 암묵적으로 리샘플링하며 라인
        # 경계마다 서브샘플 단위 반올림 오차가 낌. combined를 첫 clip과 동일한
        # 포맷으로 만들어서 이 리샘플링 자체를 없앰.
        if combined is None:
            combined = AudioSegment.silent(
                duration=0, frame_rate=clip.frame_rate
            ).set_channels(clip.channels).set_sample_width(clip.sample_width)
        gap = AudioSegment.silent(
            duration=GAP_BETWEEN_LINES_MS, frame_rate=combined.frame_rate
        ).set_channels(combined.channels).set_sample_width(combined.sample_width)

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

    combined = combined if combined is not None else AudioSegment.empty()
    return combined, BriefingManifest(
        duration_sec=combined.duration_seconds, segments=segments
    )
