import asyncio
from dataclasses import dataclass, field
from datetime import datetime

from script_app.ai_client import AiClient
from script_app.models import (
    NewsArticle,
    Section,
    SectionTargetType,
    SectionType,
    StockScript,
)
from script_app.repositories import (
    NewsRepository,
    ScriptRepository,
    SectionLineData,
    SectionRepository,
)
from script_app.schemas import AiScriptLine, CommonSectionAiResponse


@dataclass
class PersonalSectionResult:
    opening: Section
    bridges: list[Section]
    closing: Section

    def assemble(
        self,
        content_sections: list[Section],
    ) -> list[Section]:
        if len(self.bridges) != max(
            len(content_sections) - 1,
            0,
        ):
            raise ValueError(
                "bridge count must be one less than "
                "content section count"
            )

        ordered_sections = [self.opening]

        for index, content_section in enumerate(content_sections):
            ordered_sections.append(content_section)

            if index < len(self.bridges):
                ordered_sections.append(self.bridges[index])

        ordered_sections.append(self.closing)
        return ordered_sections


class PersonalSectionService:
    def __init__(
        self,
        section_repository: SectionRepository,
        ai_client: AiClient,
    ) -> None:
        self.section_repository = section_repository
        self.ai_client = ai_client

    async def generate_sections(
        self,
        content_sections: list[Section],
        period_start: datetime,
        period_end: datetime,
    ) -> PersonalSectionResult:
        if not content_sections:
            raise ValueError(
                "content_sections must not be empty"
            )

        lines_by_section = (
            self.section_repository.find_lines_by_section_ids(
                [section.id for section in content_sections]
            )
        )
        source = self._build_source(
            content_sections,
            lines_by_section,
        )
        response = await self.ai_client.generate_personal_sections(
            source,
            content_section_count=len(content_sections),
        )

        opening = self._save_personal_section(
            section_type=SectionType.OPENING,
            response_lines=response.opening,
            period_start=period_start,
            period_end=period_end,
        )
        bridges = [
            self._save_personal_section(
                section_type=SectionType.BRIDGE,
                response_lines=bridge_lines,
                period_start=period_start,
                period_end=period_end,
            )
            for bridge_lines in response.bridges
        ]
        closing = self._save_personal_section(
            section_type=SectionType.CLOSING,
            response_lines=response.closing,
            period_start=period_start,
            period_end=period_end,
        )

        return PersonalSectionResult(
            opening=opening,
            bridges=bridges,
            closing=closing,
        )

    def _save_personal_section(
        self,
        section_type: SectionType,
        response_lines: list[AiScriptLine],
        period_start: datetime,
        period_end: datetime,
    ) -> Section:
        section = Section(
            section_type=section_type,
            target_type=SectionTargetType.USER,
            stock_code=None,
            industry_code=None,
            period_start=period_start,
            period_end=period_end,
        )
        lines = [
            SectionLineData(
                talker=line.talker.value,
                content=line.content,
            )
            for line in response_lines
        ]
        return self.section_repository.save_with_lines(
            section,
            lines,
        )

    @staticmethod
    def _build_source(
        content_sections: list[Section],
        lines_by_section: dict,
    ) -> str:
        parts = [
            f"콘텐츠 섹션 수: {len(content_sections)}",
            "다음 순서의 콘텐츠를 자연스럽게 연결하세요.",
        ]

        for index, section in enumerate(
            content_sections,
            start=1,
        ):
            target_code = (
                section.industry_code
                if section.section_type == SectionType.INDUSTRY
                else section.stock_code
            )
            section_lines = lines_by_section.get(section.id, [])
            lines_text = "\n".join(
                f"{line.talker}: {line.content}"
                for line in section_lines
            )
            parts.append(
                "\n".join(
                    [
                        f"콘텐츠 {index}",
                        f"유형: {section.section_type.value}",
                        f"대상 코드: {target_code}",
                        lines_text,
                    ]
                )
            )

        return "\n\n".join(parts)


@dataclass
class CommonSectionResult:
    stock_sections: dict[str, Section] = field(
        default_factory=dict
    )
    industry_sections: dict[str, Section] = field(
        default_factory=dict
    )
    no_news_stock_codes: set[str] = field(default_factory=set)
    no_news_industry_codes: set[str] = field(default_factory=set)
    failed_stock_codes: set[str] = field(default_factory=set)
    failed_industry_codes: set[str] = field(default_factory=set)


class CommonSectionService:
    def __init__(
        self,
        news_repository: NewsRepository,
        section_repository: SectionRepository,
        ai_client: AiClient,
        max_concurrency: int = 5,
    ) -> None:
        if max_concurrency <= 0:
            raise ValueError(
                "max_concurrency must be greater than 0"
            )

        self.news_repository = news_repository
        self.section_repository = section_repository
        self.ai_client = ai_client
        self.semaphore = asyncio.Semaphore(max_concurrency)

    async def prepare_sections(
        self,
        stock_codes: list[str],
        industry_codes: list[str],
        period_start: datetime,
        period_end: datetime,
    ) -> CommonSectionResult:
        unique_stock_codes = list(dict.fromkeys(stock_codes))
        unique_industry_codes = list(
            dict.fromkeys(industry_codes)
        )
        result = CommonSectionResult(
            stock_sections=(
                self.section_repository.find_stock_sections(
                    unique_stock_codes,
                    period_start=period_start,
                    period_end=period_end,
                )
            ),
            industry_sections=(
                self.section_repository.find_industry_sections(
                    unique_industry_codes,
                    period_start=period_start,
                    period_end=period_end,
                )
            ),
        )

        missing_stock_codes = [
            code
            for code in unique_stock_codes
            if code not in result.stock_sections
        ]
        missing_industry_codes = [
            code
            for code in unique_industry_codes
            if code not in result.industry_sections
        ]
        news_by_stock = self.news_repository.find_by_stock_codes(
            missing_stock_codes,
            start_at=period_start,
            end_at=period_end,
        )
        news_by_industry = (
            self.news_repository.find_by_industry_codes(
                missing_industry_codes,
                start_at=period_start,
                end_at=period_end,
            )
        )

        targets: list[
            tuple[SectionType, str, list[NewsArticle]]
        ] = []
        self._collect_targets(
            section_type=SectionType.STOCK,
            codes=missing_stock_codes,
            news_by_code=news_by_stock,
            targets=targets,
            no_news_codes=result.no_news_stock_codes,
        )
        self._collect_targets(
            section_type=SectionType.INDUSTRY,
            codes=missing_industry_codes,
            news_by_code=news_by_industry,
            targets=targets,
            no_news_codes=result.no_news_industry_codes,
        )

        responses = await asyncio.gather(
            *[
                self._generate_response(
                    section_type=section_type,
                    target_code=target_code,
                    news_articles=news_articles,
                )
                for section_type, target_code, news_articles in targets
            ],
            return_exceptions=True,
        )

        for target, response in zip(targets, responses):
            section_type, target_code, _ = target

            if isinstance(response, Exception):
                self._failed_codes(result, section_type).add(
                    target_code
                )
                continue

            section = self._save_section(
                section_type=section_type,
                target_code=target_code,
                period_start=period_start,
                period_end=period_end,
                response=response,
            )
            self._section_map(result, section_type)[
                target_code
            ] = section

        return result

    async def _generate_response(
        self,
        section_type: SectionType,
        target_code: str,
        news_articles: list[NewsArticle],
    ) -> CommonSectionAiResponse:
        source = self._build_source(
            section_type=section_type,
            target_code=target_code,
            news_articles=news_articles,
        )

        async with self.semaphore:
            return await self.ai_client.generate_common_section(
                source
            )

    def _save_section(
        self,
        section_type: SectionType,
        target_code: str,
        period_start: datetime,
        period_end: datetime,
        response: CommonSectionAiResponse,
    ) -> Section:
        is_stock = section_type == SectionType.STOCK
        section = Section(
            section_type=section_type,
            target_type=(
                SectionTargetType.STOCK
                if is_stock
                else SectionTargetType.INDUSTRY
            ),
            stock_code=target_code if is_stock else None,
            industry_code=None if is_stock else target_code,
            period_start=period_start,
            period_end=period_end,
        )
        lines = [
            SectionLineData(
                talker=line.talker.value,
                content=line.content,
            )
            for line in response.lines
        ]
        return self.section_repository.save_with_lines(
            section,
            lines,
        )

    @staticmethod
    def _collect_targets(
        section_type: SectionType,
        codes: list[str],
        news_by_code: dict[str, list[NewsArticle]],
        targets: list[
            tuple[SectionType, str, list[NewsArticle]]
        ],
        no_news_codes: set[str],
    ) -> None:
        for code in codes:
            news_articles = news_by_code.get(code, [])

            if news_articles:
                targets.append(
                    (section_type, code, news_articles)
                )
            else:
                no_news_codes.add(code)

    @staticmethod
    def _build_source(
        section_type: SectionType,
        target_code: str,
        news_articles: list[NewsArticle],
    ) -> str:
        target_label = (
            "종목 코드"
            if section_type == SectionType.STOCK
            else "업종 코드"
        )
        parts = [
            f"{target_label}: {target_code}",
            "지정 기간의 뉴스 요약:",
        ]

        for index, article in enumerate(news_articles, start=1):
            parts.append(
                "\n".join(
                    [
                        f"뉴스 {index}",
                        f"제목: {article.title}",
                        f"요약: {article.body}",
                    ]
                )
            )

        return "\n\n".join(parts)

    @staticmethod
    def _section_map(
        result: CommonSectionResult,
        section_type: SectionType,
    ) -> dict[str, Section]:
        if section_type == SectionType.STOCK:
            return result.stock_sections

        return result.industry_sections

    @staticmethod
    def _failed_codes(
        result: CommonSectionResult,
        section_type: SectionType,
    ) -> set[str]:
        if section_type == SectionType.STOCK:
            return result.failed_stock_codes

        return result.failed_industry_codes


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
