import pytest

from app.characters import CHARACTER_VOICES, voice_for


def test_voice_for_known_speaker():
    assert voice_for("코스") == CHARACTER_VOICES["코스"]
    assert voice_for("코미") == CHARACTER_VOICES["코미"]


def test_voice_for_unknown_speaker_raises():
    with pytest.raises(ValueError):
        voice_for("모르는화자")
