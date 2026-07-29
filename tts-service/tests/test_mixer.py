from tts_app.audio.mixer import merge
from tts_app.script.models import DialogueLine
from tts_app.tts.synthesizer import LineAudio, WordTiming
from pydub import AudioSegment
from pydub.generators import Sine
from pydub.silence import detect_leading_silence


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


def test_merge_strips_leading_encoder_priming_silence():
    # mp3 인코딩 왕복 때문에 clip 앞부분에 프라이밍 무음이 남는 상황을 흉내냄.
    # words[0].startSec은 0초(=발화 시작점)를 가리키므로, 실제 합본 오디오에서도
    # 그 지점 근처에 발화가 시작돼야 한다 - 프라이밍 무음이 안 잘리면 실제
    # 오디오가 words 타이밍보다 늦게 나와 하이라이트가 앞서가는 것처럼 들린다.
    speech = Sine(440).to_audio_segment(duration=1000)
    padded = AudioSegment.silent(duration=30) + speech
    buffer = padded.export(format="mp3")
    line = LineAudio(
        line=DialogueLine(speaker="코스", text="코스 대사"),
        audio=buffer.read(),
        audio_format="mp3",
        words=[WordTiming(text="코스 대사", start_sec=0.0, end_sec=1.0)],
        audio_duration=1.0,
    )

    combined, manifest = merge([line])

    segment = manifest.segments[0]
    start_ms = int(segment.start_sec * 1000)
    end_ms = int((segment.start_sec + 1.0) * 1000)
    clip = combined[start_ms:end_ms]

    leading_silence_ms = detect_leading_silence(
        clip, silence_threshold=-40, chunk_size=5
    )
    assert leading_silence_ms < 15
