import asyncio

from app.ai_client import create_openai_client


async def main() -> None:
    ai_client = create_openai_client()

    source = """
종목 ID: 1

다음은 해당 종목과 관련된 뉴스 요약입니다.

[뉴스 1]
제목: 삼성전자, 반도체 설비 투자 확대
요약: 삼성전자가 차세대 반도체 생산 확대를 위해
설비 투자를 늘리기로 했다.

[뉴스 2]
제목: 메모리 반도체 가격 상승 전망
요약: 주요 시장조사업체는 메모리 수요 증가로
가격이 상승할 가능성이 있다고 전망했다.
""".strip()

    result = await ai_client.generate_script(source)

    print("=== 생성 결과 ===")
    print(result)


if __name__ == "__main__":
    asyncio.run(main())
