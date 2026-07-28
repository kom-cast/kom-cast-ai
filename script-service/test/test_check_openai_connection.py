from scripts.check_openai_connection import (
    DEFAULT_NEWS_FILE,
    SAMPLE_TARGETS,
    build_common_source,
    build_personal_source,
    load_sample_targets,
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
    assert "대상: 전기·전자" in source
    assert "지수값: 12345.67" in source
    assert "등락: 1.01% 상승" in source
    assert "대상: SK하이닉스" in source
    assert "종가: 210000원" in source
    assert "등락: 0.75% 하락" in source
    assert "대상: LG전자" in source
    assert "종가: 98700원" in source
    assert "등락: 1.20% 상승" in source
    assert "대상: 삼성전자" in source
    assert "종가: 270000원" in source
    assert "등락: 3.65% 상승" in source


def test_load_sample_targets_groups_and_limits_news(
    tmp_path,
) -> None:
    news_file = tmp_path / "news.csv"
    news_file.write_text(
        "\n".join(
            [
                '삼성전자,"삼성 제목 1","삼성 요약 1"',
                '삼성전자,"삼성 제목 2","삼성 요약 2"',
                'SK하이닉스,"하이닉스 제목","하이닉스 요약"',
                'LG전자,"엘지 제목","엘지 요약"',
                '전기·전자,"업종 제목","업종 요약"',
            ]
        ),
        encoding="utf-8",
    )

    targets = load_sample_targets(
        news_file,
        max_news_per_target=1,
    )
    news_by_name = {
        target.name: target.news for target in targets
    }

    assert len(targets) == 4
    assert news_by_name["삼성전자"] == (
        ("삼성 제목 1", "삼성 요약 1"),
    )
    assert news_by_name["SK하이닉스"] == (
        ("하이닉스 제목", "하이닉스 요약"),
    )
    assert news_by_name["LG전자"] == (
        ("엘지 제목", "엘지 요약"),
    )
    assert news_by_name["전기·전자"] == (
        ("업종 제목", "업종 요약"),
    )
    samsung_source = build_common_source(
        next(
            target
            for target in targets
            if target.name == "삼성전자"
        )
    )
    assert "뉴스 1" in samsung_source
    assert "제목: 삼성 제목 1" in samsung_source
    assert "요약: 삼성 요약 1" in samsung_source


def test_default_news_file_contains_ten_news_per_target() -> None:
    targets = load_sample_targets(DEFAULT_NEWS_FILE)

    assert {
        target.name: len(target.news)
        for target in targets
    } == {
        "전기·전자": 10,
        "SK하이닉스": 10,
        "LG전자": 10,
        "삼성전자": 10,
    }
