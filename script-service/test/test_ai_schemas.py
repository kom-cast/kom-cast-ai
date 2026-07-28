import pytest
from pydantic import ValidationError

from script_app.schemas import (
    CommonSectionAiResponse,
    PersonalSectionsAiResponse,
    ScriptTalker,
)


def line(talker: str = "코스", content: str = "발화 내용") -> dict:
    return {
        "talker": talker,
        "content": content,
    }


def test_common_section_response_accepts_valid_lines() -> None:
    response = CommonSectionAiResponse(
        lines=[
            line("코스", "주요 소식을 살펴보겠습니다."),
            line("코미", "뉴스 내용을 설명하겠습니다."),
        ]
    )

    assert response.lines[0].talker == ScriptTalker.KOS
    assert response.lines[1].talker == ScriptTalker.KOMI


def test_ai_response_rejects_unknown_talker() -> None:
    with pytest.raises(ValidationError):
        CommonSectionAiResponse(
            lines=[line("진행자", "주요 소식입니다.")]
        )


@pytest.mark.parametrize("content", ["", "  ", "\n"])
def test_ai_response_rejects_empty_content(content: str) -> None:
    with pytest.raises(
        ValidationError,
        match="content must not be empty",
    ):
        CommonSectionAiResponse(
            lines=[line(content=content)]
        )


def test_ai_response_trims_line_content() -> None:
    response = CommonSectionAiResponse(
        lines=[line(content="  주요 소식입니다.  ")]
    )

    assert response.lines[0].content == "주요 소식입니다."


def test_common_section_response_requires_lines() -> None:
    with pytest.raises(ValidationError):
        CommonSectionAiResponse(lines=[])


def test_personal_response_validates_bridge_count() -> None:
    response = PersonalSectionsAiResponse(
        opening=[line(content="브리핑을 시작하겠습니다.")],
        bridges=[
            [line(content="다음 업종으로 넘어가겠습니다.")],
            [line(content="이어서 종목 소식입니다.")],
        ],
        closing=[line("코미", "오늘 내용을 마무리하겠습니다.")],
    )

    validated = response.validate_bridge_count(
        content_section_count=3
    )

    assert validated is response


def test_personal_response_rejects_wrong_bridge_count() -> None:
    response = PersonalSectionsAiResponse(
        opening=[line(content="브리핑을 시작하겠습니다.")],
        bridges=[],
        closing=[line("코미", "오늘 내용을 마무리하겠습니다.")],
    )

    with pytest.raises(
        ValueError,
        match="bridge count must be one less",
    ):
        response.validate_bridge_count(content_section_count=2)


def test_personal_response_rejects_empty_bridge() -> None:
    with pytest.raises(ValidationError):
        PersonalSectionsAiResponse(
            opening=[line(content="브리핑을 시작하겠습니다.")],
            bridges=[[]],
            closing=[
                line("코미", "오늘 내용을 마무리하겠습니다.")
            ],
        )


@pytest.mark.parametrize("field_name", ["opening", "closing"])
def test_personal_response_requires_opening_and_closing(
    field_name: str,
) -> None:
    values = {
        "opening": [line(content="브리핑을 시작하겠습니다.")],
        "bridges": [],
        "closing": [
            line("코미", "오늘 내용을 마무리하겠습니다.")
        ],
    }
    values[field_name] = []

    with pytest.raises(ValidationError):
        PersonalSectionsAiResponse(**values)
