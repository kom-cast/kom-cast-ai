CHARACTER_VOICES: dict[str, str] = {
    "코스": "tc_68d4b115f0486108a7eefb37",
    "코미": "tc_6731b3ac075b04a944644234",
}


def voice_for(speaker: str) -> str:
    try:
        return CHARACTER_VOICES[speaker]
    except KeyError:
        raise ValueError(f"등록되지 않은 화자입니다: {speaker}") from None
