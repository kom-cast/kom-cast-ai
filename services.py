from dataclasses import dataclass
from datetime import datetime

from database import create_session
from models import News, NewsSummary, Script
from repositories import (
    NewsRepository,
    ScriptRepository,
    SummaryRepository,
)


@dataclass
class SummaryResult:
    created_count: int
    skipped_count: int


class SummaryService:
    def __init__(self):
        self.news_repository = NewsRepository()
        self.summary_repository = SummaryRepository()

    def summarize_unsummarized_news(self) -> SummaryResult:
        with create_session() as session:
            news_list = self.news_repository.find_unsummarized(session)

            for news in news_list:
                summary_content = self._generate_summary(news)

                summary = NewsSummary(
                    news_id=news.id,
                    content=summary_content,
                )

                self.summary_repository.save(session, summary)

            session.commit()

            return SummaryResult(
                created_count=len(news_list),
                skipped_count=0,
            )

    def get_all_summaries(self) -> list[NewsSummary]:
        with create_session() as session:
            return self.summary_repository.find_all(session)

    @staticmethod
    def _generate_summary(news: News) -> str:
        """
        현재는 시안용 가짜 요약.
        추후 OpenAI 등의 LLM 호출로 교체한다.
        """
        normalized = " ".join(news.content.split())

        if len(normalized) <= 100:
            return normalized

        return normalized[:100] + "..."


class ScriptService:
    def __init__(self):
        self.news_repository = NewsRepository()
        self.script_repository = ScriptRepository()

    def create_script(
        self,
        start_at: datetime | None = None,
        end_at: datetime | None = None,
        topic: str | None = None,
    ) -> Script:
        with create_session() as session:
            news_list = self.news_repository.find_by_filter(
                session=session,
                start_at=start_at,
                end_at=end_at,
                topic=topic,
            )

            if not news_list:
                raise ValueError("스크립트에 사용할 요약본이 없습니다.")

            script_content = self._generate_script(news_list)

            script = Script(content=script_content)
            self.script_repository.save(session, script)

            session.commit()
            session.refresh(script)

            return script

    @staticmethod
    def _generate_script(news_list: list[News]) -> str:
        """
        현재는 템플릿 기반 생성.
        추후 LLM 호출로 교체한다.
        """
        sections: list[str] = [
            "안녕하세요. 오늘의 KomCast 뉴스 브리핑입니다.",
            "",
            f"오늘은 총 {len(news_list)}개의 뉴스를 살펴보겠습니다.",
            "",
        ]

        for index, news in enumerate(news_list, start=1):
            sections.extend(
                [
                    f"{index}번째 소식입니다.",
                    news.title,
                    news.summary.content,
                    "",
                ]
            )

        sections.extend(
            [
                "지금까지 오늘의 주요 뉴스를 살펴봤습니다.",
                "KomCast 뉴스 브리핑이었습니다.",
            ]
        )

        return "\n".join(sections)
