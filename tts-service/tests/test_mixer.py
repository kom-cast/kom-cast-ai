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
    )


def test_merge_offsets_are_cumulative():
    first = _fake_line_audio("코스", "코스 대사", seconds=1.0)
    second = _fake_line_audio("코미", "코미 대사", seconds=1.0)

    combined, manifest = merge([first, second])

    assert isinstance(combined, AudioSegment)
    assert manifest.segments[0].start_sec == 0.0
    assert manifest.segments[1].start_sec > 1.0  # 1번째 라인 길이 + 화자 간 간격
    assert manifest.segments[1].words[0]["startSec"] == manifest.segments[1].start_sec
