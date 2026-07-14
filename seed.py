from datetime import datetime

from database import create_session
from models import News
from repositories import NewsRepository

# 이 클래스는 뉴스 하드코딩을 위해 존재
INITIAL_NEWS = [
    News(
        title="엔비디아, 차세대 AI 가속기 공개",
        content=(
            "엔비디아가 차세대 AI 가속기를 공개했다. "
            "신제품은 기존 제품보다 AI 연산 성능과 전력 효율이 개선됐다. "
            "글로벌 클라우드 기업들이 데이터센터 도입을 검토하고 있다."
        ),
        published_at=datetime(2026, 7, 14, 8, 30),
    ),
    News(
        title="HBM 시장 성장 전망",
        content=(
            "생성형 AI 투자 확대에 따라 고대역폭 메모리 시장이 "
            "빠르게 성장할 것으로 전망된다. "
            "삼성전자와 SK하이닉스는 생산 능력 확대를 추진하고 있다."
        ),
        published_at=datetime(2026, 7, 14, 10, 0),
    ),
    News(
        title="미국, AI 반도체 수출 규제 검토",
        content=(
            "미국 정부가 일부 국가를 대상으로 AI 반도체 수출 규제를 "
            "강화하는 방안을 검토하고 있다. "
            "구체적인 적용 대상과 시행 시기는 아직 확정되지 않았다."
        ),
        published_at=datetime(2026, 7, 14, 11, 20),
    ),
]


def seed_news() -> None:
    repository = NewsRepository()

    with create_session() as session:
        # Streamlit 재실행 시 중복 삽입 방지
        if repository.count(session) > 0:
            return

        repository.save_all(session, INITIAL_NEWS)
        session.commit()