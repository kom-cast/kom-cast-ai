import argparse
import asyncio
import csv
from dataclasses import dataclass
from pathlib import Path

from script_app.ai_client import AiClient, create_openai_client
from script_app.schemas import AiScriptLine


@dataclass(frozen=True)
class SampleTarget:
    target_type: str
    code: str
    name: str
    news: tuple[tuple[str, str], ...]
    traded_at: str
    price_label: str
    price_value: str
    change: str


SAMPLE_TARGETS = (
    SampleTarget(
        target_type="INDUSTRY",
        code="13",
        name="전기·전자",
        news=(),
        traded_at="2026-07-22T15:00:00+00:00",
        price_label="지수값",
        price_value="12345.67",
        change="1.01% 상승",
    ),
    SampleTarget(
        target_type="STOCK",
        code="000660",
        name="SK하이닉스",
        news=(),
        traded_at="2026-07-22T15:00:00+00:00",
        price_label="종가",
        price_value="210000원",
        change="0.75% 하락",
    ),
    SampleTarget(
        target_type="STOCK",
        code="066570",
        name="LG전자",
        news=(),
        traded_at="2026-07-22T15:00:00+00:00",
        price_label="종가",
        price_value="98700원",
        change="1.20% 상승",
    ),
    SampleTarget(
        target_type="STOCK",
        code="005930",
        name="삼성전자",
        news=(),
        traded_at="2026-07-22T15:00:00+00:00",
        price_label="종가",
        price_value="270000원",
        change="3.65% 상승",
    ),
)

DEFAULT_NEWS_FILE = (
    Path(__file__).parent
    / "sample_data"
    / "openai_connection_news.csv"
)


def load_sample_targets(
    news_file: Path,
    max_news_per_target: int | None = None,
) -> tuple[SampleTarget, ...]:
    if (
        max_news_per_target is not None
        and max_news_per_target < 1
    ):
        raise ValueError("max_news_per_target must be positive")

    news_by_target: dict[str, list[tuple[str, str]]] = {
        target.name: [] for target in SAMPLE_TARGETS
    }

    with news_file.open(
        "r",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        rows = csv.reader(file)

        for row_number, row in enumerate(rows, start=1):
            if len(row) != 3:
                raise ValueError(
                    f"뉴스 파일 {row_number}행은 "
                    "대상, 제목, 요약 3개 열이어야 합니다."
                )

            target_name, title, summary = (
                value.strip() for value in row
            )
            target_news = news_by_target.get(target_name)

            if (
                target_news is not None
                and (
                    max_news_per_target is None
                    or len(target_news)
                    < max_news_per_target
                )
            ):
                target_news.append((title, summary))

    missing_targets = [
        name
        for name, news in news_by_target.items()
        if not news
    ]

    if missing_targets:
        raise ValueError(
            "뉴스가 없는 관심 대상: "
            + ", ".join(missing_targets)
        )

    return tuple(
        SampleTarget(
            target_type=target.target_type,
            code=target.code,
            name=target.name,
            news=tuple(news_by_target[target.name]),
            traded_at=target.traded_at,
            price_label=target.price_label,
            price_value=target.price_value,
            change=target.change,
        )
        for target in SAMPLE_TARGETS
    )


def build_common_source(target: SampleTarget) -> str:
    target_label = (
        "업종 코드"
        if target.target_type == "INDUSTRY"
        else "종목 코드"
    )
    parts = [
        f"{target_label}: {target.code}",
        f"대상 이름: {target.name}",
        "지정 기간의 뉴스 요약:",
    ]

    for index, (title, summary) in enumerate(
        target.news,
        start=1,
    ):
        parts.append(
            "\n".join(
                [
                    f"뉴스 {index}",
                    f"제목: {title}",
                    f"요약: {summary}",
                ]
            )
        )

    return "\n\n".join(parts)


def build_personal_source(
    targets: tuple[SampleTarget, ...],
    common_lines: list[list[AiScriptLine]],
) -> str:
    parts = [
        f"콘텐츠 섹션 수: {len(targets)}",
        "다음 순서의 콘텐츠를 자연스럽게 연결하세요.",
        "오프닝에 반영할 최근 시세 현황:",
    ]

    for target in targets:
        price_type = (
            "업종 시세"
            if target.target_type == "INDUSTRY"
            else "종목 시세"
        )
        code_label = (
            "업종 코드"
            if target.target_type == "INDUSTRY"
            else "종목 코드"
        )
        parts.append(
            "\n".join(
                [
                    price_type,
                    f"대상: {target.name}",
                    f"{code_label}: {target.code}",
                    f"기준 시각: {target.traded_at}",
                    f"{target.price_label}: {target.price_value}",
                    f"등락: {target.change}",
                ]
            )
        )

    for index, (target, lines) in enumerate(
        zip(targets, common_lines),
        start=1,
    ):
        lines_text = "\n".join(
            f"{line.talker.value}: {line.content}"
            for line in lines
        )
        parts.append(
            "\n".join(
                [
                    f"콘텐츠 {index}",
                    f"유형: {target.target_type}",
                    f"대상 코드: {target.code}",
                    f"대상 이름: {target.name}",
                    lines_text,
                ]
            )
        )

    return "\n\n".join(parts)


async def generate_sample_briefing(
    ai_client: AiClient,
    targets: tuple[SampleTarget, ...] = SAMPLE_TARGETS,
) -> list[AiScriptLine]:
    common_responses = [
        await ai_client.generate_common_section(
            build_common_source(target)
        )
        for target in targets
    ]
    common_lines = [
        response.lines
        for response in common_responses
    ]
    personal_response = (
        await ai_client.generate_personal_sections(
            build_personal_source(
                targets,
                common_lines,
            ),
            content_section_count=len(targets),
        )
    )
    briefing_lines = list(personal_response.opening)

    for index, lines in enumerate(common_lines):
        briefing_lines.extend(lines)

        if index < len(personal_response.bridges):
            briefing_lines.extend(
                personal_response.bridges[index]
            )

    briefing_lines.extend(personal_response.closing)
    return briefing_lines


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--news-file",
        type=Path,
        default=DEFAULT_NEWS_FILE,
        help="대상, 제목, 요약 순서의 헤더 없는 CSV 파일",
    )
    parser.add_argument(
        "--max-news-per-target",
        type=int,
        help=(
            "대상별 최대 뉴스 수. 생략하면 파일의 뉴스를 "
            "모두 사용합니다."
        ),
    )
    args = parser.parse_args()
    targets = load_sample_targets(
        args.news_file,
        args.max_news_per_target,
    )
    ai_client = create_openai_client(profile="check")
    briefing_lines = await generate_sample_briefing(
        ai_client,
        targets,
    )

    print("=== 맞춤형 브리핑 생성 결과 ===")
    print(
        "사용 뉴스: "
        + ", ".join(
            f"{target.name} {len(target.news)}건"
            for target in targets
        )
    )

    for line in briefing_lines:
        print(f"{line.talker.value}: {line.content}")


if __name__ == "__main__":
    asyncio.run(main())
