import asyncio

from script_app.ai_client import create_openai_client


async def main() -> None:
    ai_client = create_openai_client()

    source = """
종목 코드: 005930
대상 이름: 삼성전자

지정 기간의 뉴스 요약:

[뉴스 1]
제목: 삼성전자, 반도체 설비 투자 확대
요약: 삼성전자가 차세대 반도체 생산 확대를 위해
설비 투자를 늘리기로 했다.

[뉴스 2]
제목: 메모리 반도체 가격 상승 전망
요약: 주요 시장조사업체는 메모리 수요 증가로
가격이 상승할 가능성이 있다고 전망했다.
""".strip()

    result = await ai_client.generate_common_section(source)

    print("=== 생성 결과 ===")
    for line in result.lines:
        print(f"{line.talker.value}: {line.content}")


if __name__ == "__main__":
    asyncio.run(main())
