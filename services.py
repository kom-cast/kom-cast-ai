from dataclasses import dataclass
from datetime import datetime

from ai_client import OpenAiClient
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
    def __init__(self) -> None:
        self.news_repository = NewsRepository()
        self.summary_repository = SummaryRepository()
        self.ai_client = OpenAiClient()

    def summarize_unsummarized_news(self) -> SummaryResult:
        with create_session() as session:
            news_list = self.news_repository.find_unsummarized(session)

            if not news_list:
                return SummaryResult(
                    created_count=0,
                    skipped_count=0,
                )

            created_count = 0
            skipped_count = 0

            for news in news_list:
                try:
                    summary_content = self.ai_client.generate_summary(news)

                    summary = NewsSummary(
                        news_id=news.id,
                        content=summary_content,
                    )

                    self.summary_repository.save(session, summary)
                    created_count += 1

                except Exception:
                    skipped_count += 1

            session.commit()

            return SummaryResult(
                created_count=created_count,
                skipped_count=skipped_count,
            )

    def get_all_summaries(self) -> list[NewsSummary]:
        with create_session() as session:
            return self.summary_repository.find_all(session)


class ScriptService:
    def __init__(self) -> None:
        self.news_repository = NewsRepository()
        self.script_repository = ScriptRepository()
        self.ai_client = OpenAiClient()

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

            script_content = self.ai_client.generate_script(news_list)

            script = Script(content=script_content)
            self.script_repository.save(session, script)

            session.commit()
            session.refresh(script)

            return script