from scripts.check_openai_connection import (
    SAMPLE_TARGETS,
    build_personal_source,
)
from script_app.schemas import AiScriptLine


def test_personal_source_contains_sample_prices() -> None:
    common_lines = [
        [
            AiScriptLine(
                talker="코스",
                content=f"{target.name} 소식입니다.",
            )
        ]
        for target in SAMPLE_TARGETS
    ]

    source = build_personal_source(
        SAMPLE_TARGETS,
        common_lines,
    )

    assert "오프닝에 반영할 최근 시세 현황:" in source
    assert "대상: 반도체" in source
    assert "지수값: 12345.67" in source
    assert "등락: 1.01% 상승" in source
    assert "대상: SK하이닉스" in source
    assert "종가: 210000원" in source
    assert "등락: 0.75% 하락" in source
    assert "대상: 삼성전자" in source
    assert "종가: 270000원" in source
    assert "등락: 3.65% 상승" in source
