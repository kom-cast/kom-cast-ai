from tts_app.audio.mixer import merge
from tts_app.script.models import DialogueLine
from tts_app.tts.synthesizer import LineAudio, WordTiming
from pydub import AudioSegment
from pydub.generators import Sine


def _fake_line_audio(speaker: str, text: str, seconds: float) -> LineAudio:
    tone = Sine(440).to_audio_segment(duration=int(seconds * 1000))
    buffer = tone.export(format="mp3")
    return LineAudio(
        line=DialogueLine(speaker=speaker, text=text),
        audio=buffer.read(),
        audio_format="mp3",
        words=[WordTiming(text=text, start_sec=0.0, end_sec=seconds)],
        audio_duration=seconds,
    )


def test_merge_offsets_are_cumulative():
    first = _fake_line_audio("코스", "코스 대사", seconds=1.0)
    second = _fake_line_audio("코미", "코미 대사", seconds=1.0)

    combined, manifest = merge([first, second])

    assert isinstance(combined, AudioSegment)
    assert manifest.segments[0].start_sec == 0.0
    assert manifest.segments[1].start_sec > 1.0  # 1번째 라인 길이 + 화자 간 간격
    assert manifest.segments[1].words[0]["startSec"] == manifest.segments[1].start_sec


def test_merge_offset_follows_audio_duration_not_decoded_length():
    # mp3 인코딩/디코딩 왕복 때문에 실제 디코드된 clip 길이(1.0초 근처, 정확히
    # 일치 안 할 수 있음)가 audio_duration(Typecast가 words 타이밍 계산에 쓴
    # "진짜" 길이, 여기선 일부러 2.0초로 크게 다르게 줌)과 어긋나더라도, 다음
    # 라인 offset은 audio_duration 기준으로 계산돼야 함.
    first = _fake_line_audio("코스", "코스 대사", seconds=1.0)
    first.audio_duration = 2.0
    second = _fake_line_audio("코미", "코미 대사", seconds=1.0)

    _, manifest = merge([first, second])

    gap_sec = 0.4
    assert manifest.segments[1].start_sec == 2.0 + gap_sec
