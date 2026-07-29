from datetime import date, datetime, timedelta, timezone
from uuid import UUID

import pytest

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
                f"고유사건{index}의 독립변화{index}와 "
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


def test_excludes_advertisements_before_backfilling_duplicates() -> None:
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
    assert len(selected) == 3
    assert product in selected


def test_backfills_similar_news_when_only_three_are_available() -> None:
    selector = NewsSelector(max_articles=3)
    higher_score = article(
        1,
        "삼성전자 HBM 생산 확대와 실적 개선",
        "삼성전자 HBM 생산 확대가 인공지능 메모리 "
        "고객 수요 대응과 매출 개선으로 이어질 전망입니다.",
    )
    lower_score = article(
        2,
        "AI 메모리 공급 능력 확충",
        "삼성전자 HBM 생산 확대가 인공지능 메모리 "
        "고객 수요 대응과 매출 개선으로 이어질 계획입니다.",
        hours_old=2,
    )
    unrelated = article(
        3,
        "삼성전자 모바일 신제품 출시",
        "삼성전자가 새로운 폴더블 스마트폰을 "
        "공개하고 판매를 시작했습니다.",
    )

    selected = selector.select(
        [lower_score, unrelated, higher_score],
        target_name="삼성전자",
        target_code="005930",
        as_of=AS_OF,
    )

    assert higher_score in selected
    assert lower_score in selected
    assert unrelated in selected


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


def test_keeps_available_news_when_direct_match_filter_would_remove_it() -> None:
    selector = NewsSelector(max_articles=3)
    unrelated = article(
        1,
        "LG이노텍 2분기 실적 개선",
        "LG이노텍의 매출과 영업이익이 증가했습니다.",
    )
    direct = article(
        2,
        "OLED TV 시장 확대",
        "LG전자 프리미엄 TV 판매에 영향을 줄 수 "
        "있으며 LG전자 제품 경쟁력과 연결되는 "
        "시장 소식입니다.",
    )

    selected = selector.select(
        [unrelated, direct],
        target_name="LG전자",
        target_code="066570",
        as_of=AS_OF,
    )

    assert set(selected) == {unrelated, direct}


def test_keeps_available_news_when_roundup_filter_would_remove_it() -> None:
    selector = NewsSelector(max_articles=3)
    roundup = article(
        1,
        "AI 산업 주요 소식 종합",
        "\n".join(
            [
                "1. 반도체 기업의 생산 투자",
                "2. 데이터센터 인프라 확대",
                "3. LG전자 냉각 장치 인증",
                "4. LG전자 사업 확대 가능성",
            ]
        ),
    )
    direct = article(
        2,
        "LG전자 액체냉각 사업 확대",
        "LG전자가 데이터센터 냉각 장치 인증을 "
        "확대했습니다.",
    )

    selected = selector.select(
        [roundup, direct],
        target_name="LG전자",
        target_code="066570",
        as_of=AS_OF,
    )

    assert set(selected) == {roundup, direct}


def test_backfills_same_event_when_only_three_are_available() -> None:
    selector = NewsSelector(max_articles=3)
    higher_score = article(
        1,
        "SK하이닉스, 반도체 쇼크에 주가 급락",
        "SK하이닉스 주가가 AI 투자 우려로 "
        "하락했습니다.",
    )
    lower_score = article(
        2,
        "SK하이닉스 약세…반도체주 동반 하락",
        "SK하이닉스를 포함한 반도체 종목이 "
        "약세를 보였습니다.",
        hours_old=2,
    )
    different_event = article(
        3,
        "SK하이닉스 HBM 공급 계약",
        "SK하이닉스가 고객사와 HBM 공급 계약을 "
        "추진합니다.",
    )

    selected = selector.select(
        [lower_score, different_event, higher_score],
        target_name="SK하이닉스",
        target_code="000660",
        as_of=AS_OF,
    )

    assert higher_score in selected
    assert lower_score in selected
    assert different_event in selected


def test_keeps_available_news_when_listing_filter_would_remove_it() -> None:
    selector = NewsSelector(max_articles=3)
    listing = article(
        1,
        (
            "SK하이닉스 -8.98%, DB하이텍 -7.80%, "
            "삼성전자 -6.10%"
        ),
        "종목별 주가 변동과 HTS 정보를 제공합니다.",
    )
    substantive = article(
        2,
        "SK하이닉스 HBM 공급 확대",
        "SK하이닉스가 고객 수요에 맞춰 HBM 생산과 "
        "공급을 확대합니다.",
    )

    selected = selector.select(
        [listing, substantive],
        target_name="SK하이닉스",
        target_code="000660",
        as_of=AS_OF,
    )

    assert set(selected) == {listing, substantive}


def test_returns_no_news_when_no_news_is_available() -> None:
    selector = NewsSelector(max_articles=3)

    selected = selector.select(
        [],
        target_name="SK하이닉스",
        target_code="000660",
        as_of=AS_OF,
    )

    assert selected == []


def test_industry_selection_does_not_require_name_mention() -> None:
    selector = NewsSelector(max_articles=3)
    mapped_industry_news = article(
        1,
        "HBM 장비 투자 확대",
        "반도체 생산 장비 공급망의 투자가 늘었습니다.",
    )

    selected = selector.select(
        [mapped_industry_news],
        target_name="전기·전자",
        target_code="13",
        as_of=AS_OF,
        require_direct_match=False,
    )

    assert selected == [mapped_industry_news]


@pytest.mark.parametrize(
    "threshold",
    [0, -0.1, 1.1],
)
def test_rejects_invalid_summary_overlap_threshold(
    threshold: float,
) -> None:
    with pytest.raises(
        ValueError,
        match="summary_overlap_threshold",
    ):
        NewsSelector(
            summary_overlap_threshold=threshold,
        )
