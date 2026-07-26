import asyncio
from datetime import datetime

from script_app.ai_client import AiClient
from script_app.models import StockScript
from script_app.repositories import NewsRepository, ScriptRepository


class ScriptService:
    def __init__(
        self,
        news_repository: NewsRepository,
        script_repository: ScriptRepository,
        ai_client: AiClient,
        max_concurrency: int = 5,
    ) -> None:
        if max_concurrency <= 0:
            raise ValueError(
                "max_concurrency must be greater than 0"
            )

        self.news_repository = news_repository
        self.script_repository = script_repository
        self.ai_client = ai_client
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def generate_scripts(
        self,
        stock_ids: list[int],
        start_at: datetime,
        end_at: datetime,
    ) -> dict[int, str]:
        """
        여러 종목의 스크립트를 동시에 생성한다.

        반환 예시:
        {
            1: "삼성전자 관련 스크립트",
            2: "SK하이닉스 관련 스크립트",
        }
        """
        if start_at >= end_at:
            raise ValueError("start_at must be earlier than end_at")

        unique_stock_ids = list(dict.fromkeys(stock_ids))

        tasks = [
            self._generate_script_by_stock(
                stock_id=stock_id,
                start_at=start_at,
                end_at=end_at,
            )
            for stock_id in unique_stock_ids
        ]

        scripts = await asyncio.gather(*tasks)

        return {
            stock_id: script
            for stock_id, script in zip(
                unique_stock_ids,
                scripts,
            )
        }

    async def _generate_script_by_stock(
        self,
        stock_id: int,
        start_at: datetime,
        end_at: datetime,
    ) -> str:
        news_summaries = (
            self.news_repository.find_news_summaries(
                stock_id=stock_id,
                start_at=start_at,
                end_at=end_at,
            )
        )

        if not news_summaries:
            return ""

        source = self._combine_news_summaries(
            stock_id=stock_id,
            news_summaries=news_summaries,
        )

        async with self.semaphore:
            generated_script = (
                await self.ai_client.generate_script(
                    source
                )
            )

        stock_script = StockScript(
            stock_id=stock_id,
            start_at=start_at,
            end_at=end_at,
            script_content=generated_script,
        )

        self.script_repository.save(stock_script)

        return generated_script

    @staticmethod
    def _combine_news_summaries(
        stock_id: int,
        news_summaries: list,
    ) -> str:
        sections = [
            f"종목 ID: {stock_id}",
            "다음은 해당 종목과 관련된 뉴스 요약입니다.",
        ]

        for index, news in enumerate(
            news_summaries,
            start=1,
        ):
            sections.append(
                "\n".join(
                    [
                        f"[뉴스 {index}]",
                        f"제목: {news.title}",
                        f"요약: {news.summary_content}",
                    ]
                )
            )

        return "\n\n".join(sections)
