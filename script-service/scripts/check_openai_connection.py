import asyncio
from dataclasses import dataclass

from script_app.ai_client import AiClient, create_openai_client
from script_app.schemas import AiScriptLine


@dataclass(frozen=True)
class SampleTarget:
    target_type: str
    code: str
    name: str
    news: tuple[tuple[str, str], ...]


SAMPLE_TARGETS = (
    SampleTarget(
        target_type="INDUSTRY",
        code="SEMI",
        name="반도체",
        news=(
            (
                "반도체 업계, 설비 투자 확대",
                "주요 반도체 기업들이 생산 설비 투자를 "
                "확대하고 있다.",
            ),
        ),
    ),
    SampleTarget(
        target_type="STOCK",
        code="000660",
        name="SK하이닉스",
        news=(
            (
                "SK하이닉스, 고대역폭 메모리 생산 확대",
                "SK하이닉스가 고대역폭 메모리 수요에 "
                "대응해 생산 확대 계획을 발표했다.",
            ),
        ),
    ),
    SampleTarget(
        target_type="STOCK",
        code="005930",
        name="삼성전자",
        news=(
            (
                "삼성전자, 반도체 설비 투자 확대",
                "삼성전자가 차세대 반도체 생산을 위한 "
                "설비 투자를 늘리기로 했다.",
            ),
            (
                "메모리 반도체 수요 증가 전망",
                "시장조사업체는 메모리 수요가 증가할 "
                "가능성이 있다고 전망했다.",
            ),
        ),
    ),
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
    ]

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
) -> list[AiScriptLine]:
    common_responses = [
        await ai_client.generate_common_section(
            build_common_source(target)
        )
        for target in SAMPLE_TARGETS
    ]
    common_lines = [
        response.lines
        for response in common_responses
    ]
    personal_response = (
        await ai_client.generate_personal_sections(
            build_personal_source(
                SAMPLE_TARGETS,
                common_lines,
            ),
            content_section_count=len(SAMPLE_TARGETS),
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
    ai_client = create_openai_client()
    briefing_lines = await generate_sample_briefing(ai_client)

    print("=== 맞춤형 브리핑 생성 결과 ===")

    for line in briefing_lines:
        print(f"{line.talker.value}: {line.content}")


if __name__ == "__main__":
    asyncio.run(main())
