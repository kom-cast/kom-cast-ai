from datetime import date, datetime, timedelta, timezone
from uuid import UUID

from script_app.models import NewsArticle
from script_app.services import NewsSelector


AS_OF = datetime(2026, 7, 23, tzinfo=timezone.utc)


def article(
    article_id: int,
    title: str,
    summary: str,
    *,
    hours_old: int = 1,
    news_code: str | None = None,
) -> NewsArticle:
    return NewsArticle(
        id=UUID(int=article_id),
        source="테스트 언론사",
        news_date=date(2026, 7, 22),
        news_code=news_code,
        published_at=AS_OF - timedelta(hours=hours_old),
        title=title,
        body=summary,
        summary=summary,
    )


def test_selects_at_most_three_important_news() -> None:
    selector = NewsSelector(max_articles=3)
    articles = [
        article(
            index,
            f"삼성전자 일반 뉴스 {index}",
            "시장 동향을 전했습니다.",
            hours_old=index,
        )
        for index in range(1, 101)
    ]
    important = article(
        101,
        "삼성전자 대규모 공급 계약",
        "삼성전자 매출과 실적에 영향을 줄 수 있는 "
        "10조원 규모 공급 계약입니다.",
    )
    articles.append(important)

    selected = selector.select(
        articles,
        target_name="삼성전자",
        target_code="005930",
        as_of=AS_OF,
    )

    assert len(selected) == 3
    assert important in selected


def test_excludes_advertisements_and_deduplicates_news() -> None:
    selector = NewsSelector(max_articles=3)
    original = article(
        1,
        "[속보] 삼성전자 반도체 투자",
        "삼성전자가 반도체 생산 투자를 확대합니다.",
        news_code="NEWS-1",
    )
    duplicate_code = article(
        2,
        "삼성전자 반도체 투자 후속",
        "같은 투자 소식입니다.",
        news_code="NEWS-1",
    )
    duplicate_title = article(
        3,
        "삼성전자 반도체 투자(종합)",
        "같은 제목의 재송 기사입니다.",
    )
    advertisement = article(
        4,
        "삼성전자 투자 기회",
        "스탁론 무료상담으로 최대 4배 투자하세요.",
    )
    product = article(
        5,
        "삼성전자 신제품 출시",
        "삼성전자가 새 제품을 출시했습니다.",
    )

    selected = selector.select(
        [
            advertisement,
            duplicate_code,
            duplicate_title,
            product,
            original,
        ],
        target_name="삼성전자",
        target_code="005930",
        as_of=AS_OF,
    )

    assert advertisement not in selected
    assert len(
        [
            item
            for item in selected
            if "반도체 투자" in item.title
        ]
    ) == 1
    assert product in selected


def test_prefers_different_topics_before_filling_same_topic() -> None:
    selector = NewsSelector(max_articles=3)
    earnings = article(
        1,
        "삼성전자 실적 발표",
        "삼성전자 매출과 영업이익이 발표됐습니다.",
    )
    second_earnings = article(
        2,
        "삼성전자 분기 실적",
        "삼성전자 수익성 전망을 다룹니다.",
    )
    contract = article(
        3,
        "삼성전자 공급 계약",
        "삼성전자가 고객사와 공급 계약을 맺었습니다.",
    )
    product = article(
        4,
        "삼성전자 신제품 출시",
        "삼성전자가 모바일 신제품을 출시했습니다.",
    )

    selected = selector.select(
        [
            earnings,
            second_earnings,
            contract,
            product,
        ],
        target_name="삼성전자",
        target_code="005930",
        as_of=AS_OF,
    )

    assert len(selected) == 3
    assert contract in selected
    assert product in selected
    assert len(
        [
            item
            for item in selected
            if "실적" in f"{item.title} {item.summary}"
        ]
    ) == 1


def test_returns_available_news_without_padding() -> None:
    selector = NewsSelector(max_articles=3)
    only_news = article(
        1,
        "삼성전자 실적 발표",
        "삼성전자가 실적을 발표했습니다.",
    )

    selected = selector.select(
        [only_news],
        target_name="삼성전자",
        target_code="005930",
        as_of=AS_OF,
    )

    assert selected == [only_news]
