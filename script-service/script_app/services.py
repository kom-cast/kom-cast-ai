import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from openai import APITimeoutError, OpenAIError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from script_app.ai_client import AiClient, AiResponseInvalidError
from script_app.models import (
    IndustryPrice,
    MarketPrice,
    NewsArticle,
    Section,
    SectionTargetType,
    SectionType,
    ScriptStatus,
)
from script_app.repositories import (
    NewsRepository,
    PriceRepository,
    SectionLineData,
    SectionRepository,
    ScriptRepository,
    SectionInUseError,
    TargetRepository,
    UserInterestRepository,
)
from script_app.schemas import (
    AiScriptLine,
    CommonSectionAiResponse,
    GeneratedScriptResult,
    GenerateUserScriptsResponse,
    ScriptFailureCode,
    ScriptFailureResult,
)

logger = logging.getLogger(__name__)


class ScriptGenerationService:
    def __init__(
        self,
        session: Session,
        user_interest_repository: UserInterestRepository,
        script_repository: ScriptRepository,
        common_section_service: "CommonSectionService",
        personal_section_service: "PersonalSectionService",
    ) -> None:
        self.session = session
        self.user_interest_repository = user_interest_repository
        self.script_repository = (
            script_repository
        )
        self.common_section_service = common_section_service
        self.personal_section_service = personal_section_service

    async def generate(
        self,
        user_ids: list[UUID],
        period_start: datetime,
        period_end: datetime,
    ) -> GenerateUserScriptsResponse:
        unique_user_ids = list(dict.fromkeys(user_ids))
        targets_by_user = (
            self.user_interest_repository.find_by_user_ids(
                unique_user_ids
            )
        )
        for user_id in unique_user_ids:
            targets = targets_by_user[user_id]
            logger.info(
                "script_generation_user_interests user_id=%s "
                "stock_codes=%s industry_codes=%s",
                user_id,
                targets.stock_codes,
                targets.industry_codes,
            )

        existing_scripts = (
            self.script_repository.find_scripts(
                unique_user_ids,
                period_start=period_start,
                period_end=period_end,
            )
        )
        scripts = [
            GeneratedScriptResult(
                script_id=script.id,
                user_id=user_id,
                reused=True,
                script_text=(
                    self.script_repository.get_script_text(
                        script.id
                    )
                ),
            )
            for user_id in unique_user_ids
            if (
                script := existing_scripts.get(user_id)
            ) is not None
            and script.status == ScriptStatus.COMPLETED
        ]
        failures = [
            self._failure(
                user_id,
                ScriptFailureCode.GENERATION_IN_PROGRESS,
                "이미 스크립트를 생성하고 있습니다.",
            )
            for user_id in unique_user_ids
            if (
                script := existing_scripts.get(user_id)
            ) is not None
            and script.status == ScriptStatus.GENERATING
        ]
        pending_user_ids = [
            user_id
            for user_id in unique_user_ids
            if (
                (script := existing_scripts.get(user_id))
                is None
                or script.status == ScriptStatus.FAILED
            )
        ]

        if not pending_user_ids:
            return GenerateUserScriptsResponse(
                scripts=scripts,
                failures=failures,
            )

        all_stock_codes = sorted(
            {
                stock_code
                for user_id in pending_user_ids
                for stock_code in targets_by_user[
                    user_id
                ].stock_codes
            }
        )
        all_industry_codes = sorted(
            {
                industry_code
                for user_id in pending_user_ids
                for industry_code in targets_by_user[
                    user_id
                ].industry_codes
            }
        )
        common_result = (
            await self.common_section_service.prepare_sections(
                stock_codes=all_stock_codes,
                industry_codes=all_industry_codes,
                period_start=period_start,
                period_end=period_end,
            )
        )
        self.session.commit()

        for user_id in pending_user_ids:
            targets = targets_by_user[user_id]

            if not targets.stock_codes and not targets.industry_codes:
                failures.append(
                    self._failure(
                        user_id,
                        ScriptFailureCode.NO_INTEREST_TARGET,
                        "관심 종목 또는 업종이 없습니다.",
                    )
                )
                continue

            if self._has_failed_target(targets, common_result):
                failures.append(
                    self._failure(
                        user_id,
                        ScriptFailureCode.AI_GENERATION_FAILED,
                        "공통 섹션 생성에 실패했습니다.",
                    )
                )
                continue

            content_sections = [
                common_result.industry_sections[industry_code]
                for industry_code in sorted(
                    targets.industry_codes
                )
                if industry_code
                in common_result.industry_sections
            ]
            content_sections.extend(
                common_result.stock_sections[stock_code]
                for stock_code in sorted(targets.stock_codes)
                if stock_code in common_result.stock_sections
            )

            if not content_sections:
                failures.append(
                    self._failure(
                        user_id,
                        ScriptFailureCode.NO_NEWS_FOUND,
                        "조회 기간에 관련 뉴스가 없습니다.",
                    )
                )
                continue

            existing_script = existing_scripts.get(user_id)

            try:
                if existing_script is not None:
                    script = (
                        self.script_repository
                        .retry_failed_script(existing_script)
                    )
                else:
                    script = (
                        self.script_repository
                        .create_generating_script(
                            user_id,
                            period_start=period_start,
                            period_end=period_end,
                        )
                    )
                self.session.commit()
            except IntegrityError:
                self.session.rollback()
                concurrent_script = (
                    self.script_repository.find_script(
                        user_id,
                        period_start=period_start,
                        period_end=period_end,
                    )
                )

                if (
                    concurrent_script is not None
                    and concurrent_script.status
                    == ScriptStatus.COMPLETED
                ):
                    scripts.append(
                        GeneratedScriptResult(
                            script_id=concurrent_script.id,
                            user_id=user_id,
                            reused=True,
                            script_text=(
                                self.script_repository
                                .get_script_text(
                                    concurrent_script.id
                                )
                            ),
                        )
                    )
                elif (
                    concurrent_script is not None
                    and concurrent_script.status
                    == ScriptStatus.GENERATING
                ):
                    failures.append(
                        self._failure(
                            user_id,
                            ScriptFailureCode.GENERATION_IN_PROGRESS,
                            "이미 스크립트를 생성하고 있습니다.",
                        )
                    )
                else:
                    failures.append(
                        self._failure(
                            user_id,
                            ScriptFailureCode.DATABASE_ERROR,
                            "스크립트 생성 준비에 실패했습니다.",
                        )
                    )
                continue
            except SQLAlchemyError:
                self.session.rollback()
                failures.append(
                    self._failure(
                        user_id,
                        ScriptFailureCode.DATABASE_ERROR,
                        "스크립트 생성 준비에 실패했습니다.",
                    )
                )
                continue

            try:
                personal_sections = (
                    await self.personal_section_service
                    .generate_sections(
                        content_sections,
                        stock_codes=targets.stock_codes,
                        industry_codes=targets.industry_codes,
                        period_start=period_start,
                        period_end=period_end,
                    )
                )
                ordered_sections = personal_sections.assemble(
                    content_sections
                )
                self.script_repository.add_sections(
                    script,
                    ordered_sections,
                )
                self.script_repository.update_status(
                    script,
                    ScriptStatus.COMPLETED,
                )
                self.session.commit()
                scripts.append(
                    GeneratedScriptResult(
                        script_id=script.id,
                        user_id=user_id,
                        reused=False,
                        script_text=(
                            self.script_repository.get_script_text(
                                script.id
                            )
                        ),
                    )
                )
            except (TimeoutError, APITimeoutError):
                self._mark_script_failed(script)
                failures.append(
                    self._failure(
                        user_id,
                        ScriptFailureCode.GENERATION_TIMEOUT,
                        "스크립트 생성 시간이 초과되었습니다.",
                    )
                )
            except AiResponseInvalidError:
                self._mark_script_failed(script)
                failures.append(
                    self._failure(
                        user_id,
                        ScriptFailureCode.AI_RESPONSE_INVALID,
                        "AI 응답 형식이 올바르지 않습니다.",
                    )
                )
            except SQLAlchemyError:
                self._mark_script_failed(script)
                failures.append(
                    self._failure(
                        user_id,
                        ScriptFailureCode.DATABASE_ERROR,
                        "스크립트 저장에 실패했습니다.",
                    )
                )
            except OpenAIError:
                self._mark_script_failed(script)
                failures.append(
                    self._failure(
                        user_id,
                        ScriptFailureCode.AI_GENERATION_FAILED,
                        "스크립트 생성에 실패했습니다.",
                    )
                )
            except Exception:
                self.session.rollback()
                raise

        return GenerateUserScriptsResponse(
            scripts=scripts,
            failures=failures,
        )

    def _mark_script_failed(
        self,
        script,
    ) -> None:
        self.session.rollback()

        try:
            self.script_repository.update_status(
                script,
                ScriptStatus.FAILED,
            )
            self.session.commit()
        except SQLAlchemyError:
            self.session.rollback()

    @staticmethod
    def _has_failed_target(
        targets,
        common_result: "CommonSectionResult",
    ) -> bool:
        return bool(
            set(targets.stock_codes)
            & common_result.failed_stock_codes
            or set(targets.industry_codes)
            & common_result.failed_industry_codes
        )

    @staticmethod
    def _failure(
        user_id: UUID,
        code: ScriptFailureCode,
        message: str,
    ) -> ScriptFailureResult:
        return ScriptFailureResult(
            user_id=user_id,
            code=code,
            message=message,
        )


class ResourceNotFoundError(Exception):
    pass


class ResourceInUseError(Exception):
    pass


class ScriptDeletionService:
    def __init__(
        self,
        session: Session,
        script_repository: ScriptRepository,
        section_repository: SectionRepository,
    ) -> None:
        self.session = session
        self.script_repository = script_repository
        self.section_repository = section_repository

    def delete_script(self, script_id: UUID) -> None:
        try:
            deleted = self.script_repository.delete_by_id(
                script_id
            )

            if not deleted:
                raise ResourceNotFoundError

            self.session.commit()
        except ResourceNotFoundError:
            self.session.rollback()
            raise
        except IntegrityError as error:
            self.session.rollback()
            raise ResourceInUseError from error
        except SQLAlchemyError:
            self.session.rollback()
            raise

    def delete_section(self, section_id: UUID) -> None:
        try:
            deleted = self.section_repository.delete_by_id(
                section_id
            )

            if not deleted:
                raise ResourceNotFoundError

            self.session.commit()
        except ResourceNotFoundError:
            self.session.rollback()
            raise
        except SectionInUseError as error:
            self.session.rollback()
            raise ResourceInUseError from error
        except IntegrityError as error:
            self.session.rollback()
            raise ResourceInUseError from error
        except SQLAlchemyError:
            self.session.rollback()
            raise


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
        price_repository: PriceRepository,
        target_repository: TargetRepository,
        ai_client: AiClient,
    ) -> None:
        self.section_repository = section_repository
        self.price_repository = price_repository
        self.target_repository = target_repository
        self.ai_client = ai_client

    async def generate_sections(
        self,
        content_sections: list[Section],
        stock_codes: list[str],
        industry_codes: list[str],
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
        unique_stock_codes = list(dict.fromkeys(stock_codes))
        unique_industry_codes = list(
            dict.fromkeys(industry_codes)
        )
        stock_prices = (
            self.price_repository.find_latest_stock_prices(
                unique_stock_codes,
                as_of=period_end,
            )
        )
        industry_prices = (
            self.price_repository.find_latest_industry_prices(
                unique_industry_codes,
                as_of=period_end,
            )
        )
        stocks = self.target_repository.find_stocks(
            unique_stock_codes
        )
        industries = self.target_repository.find_industries(
            unique_industry_codes
        )
        source = self._build_source(
            content_sections,
            lines_by_section,
            stock_prices=stock_prices,
            industry_prices=industry_prices,
            stock_names={
                code: stock.corp_name
                for code, stock in stocks.items()
            },
            industry_names={
                code: industry.industry_name
                for code, industry in industries.items()
            },
            stock_codes=unique_stock_codes,
            industry_codes=unique_industry_codes,
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
        stock_prices: dict[str, MarketPrice],
        industry_prices: dict[str, IndustryPrice],
        stock_names: dict[str, str],
        industry_names: dict[str, str],
        stock_codes: list[str],
        industry_codes: list[str],
    ) -> str:
        parts = [
            f"콘텐츠 섹션 수: {len(content_sections)}",
            "다음 순서의 콘텐츠를 자연스럽게 연결하세요.",
        ]
        price_parts = PersonalSectionService._build_price_parts(
            stock_prices=stock_prices,
            industry_prices=industry_prices,
            stock_names=stock_names,
            industry_names=industry_names,
            stock_codes=stock_codes,
            industry_codes=industry_codes,
        )

        if price_parts:
            parts.extend(
                [
                    "오프닝에 반영할 최근 시세 현황:",
                    *price_parts,
                ]
            )

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

    @staticmethod
    def _build_price_parts(
        stock_prices: dict[str, MarketPrice],
        industry_prices: dict[str, IndustryPrice],
        stock_names: dict[str, str],
        industry_names: dict[str, str],
        stock_codes: list[str],
        industry_codes: list[str],
    ) -> list[str]:
        parts = []

        for industry_code in industry_codes:
            price = industry_prices.get(industry_code)

            if price is not None:
                parts.append(
                    "\n".join(
                        [
                            "업종 시세",
                            (
                                "대상: "
                                f"{industry_names.get(industry_code, industry_code)}"
                            ),
                            f"업종 코드: {industry_code}",
                            (
                                "기준 시각: "
                                f"{price.traded_at.isoformat()}"
                            ),
                            (
                                "지수값: "
                                f"{PersonalSectionService._format_number(price.index_value)}"
                            ),
                            (
                                "등락: "
                                f"{PersonalSectionService._format_change(price.change_rate)}"
                            ),
                        ]
                    )
                )

        for stock_code in stock_codes:
            price = stock_prices.get(stock_code)

            if price is not None:
                parts.append(
                    "\n".join(
                        [
                            "종목 시세",
                            (
                                "대상: "
                                f"{stock_names.get(stock_code, stock_code)}"
                            ),
                            f"종목 코드: {stock_code}",
                            (
                                "기준 시각: "
                                f"{price.traded_at.isoformat()}"
                            ),
                            (
                                "종가: "
                                f"{PersonalSectionService._format_number(price.close_price)}원"
                            ),
                            (
                                "등락: "
                                f"{PersonalSectionService._format_change(price.change_rate)}"
                            ),
                        ]
                    )
                )

        return parts

    @staticmethod
    def _format_number(value) -> str:
        formatted = format(value, "f")

        if "." in formatted:
            formatted = formatted.rstrip("0").rstrip(".")

        return formatted

    @staticmethod
    def _format_change(value) -> str:
        rate = PersonalSectionService._format_number(abs(value))

        if value > 0:
            return f"{rate}% 상승"

        if value < 0:
            return f"{rate}% 하락"

        return "보합"


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


@dataclass(frozen=True)
class RankedNews:
    article: NewsArticle
    score: int
    topic: str


class NewsSelector:
    ADVERTISEMENT_KEYWORDS = (
        "스탁론",
        "무료상담",
        "최저금리",
        "최대 4배",
        "계좌 부스터",
        "수익률 인증",
        "급등주 추천",
    )
    GENERIC_TITLE_KEYWORDS = (
        "인기검색",
        "순매수 상위종목",
        "오늘의 이슈&테마",
        "주요이슈 점검",
    )
    LISTING_SUMMARY_KEYWORDS = (
        "증권사 HTS",
        "인포스탁 홈페이지",
        "종목명 및 주가 변동",
        "상위 종목 현황",
    )
    MATERIAL_KEYWORDS = {
        "실적": 12,
        "영업이익": 12,
        "매출": 10,
        "수주": 12,
        "공급 계약": 12,
        "계약": 8,
        "투자": 7,
        "증설": 10,
        "생산": 7,
        "인수": 10,
        "합병": 10,
        "유상증자": 10,
        "배당": 10,
        "출시": 7,
        "인증": 7,
        "소송": 10,
        "제재": 10,
        "리콜": 10,
    }
    TOPIC_KEYWORDS = (
        (
            "EARNINGS",
            ("실적", "매출", "영업이익", "수익성"),
        ),
        (
            "CONTRACT",
            ("수주", "공급 계약", "계약", "고객"),
        ),
        (
            "INVESTMENT",
            ("투자", "증설", "생산", "공장"),
        ),
        (
            "PRODUCT",
            ("출시", "신제품", "인증", "서비스"),
        ),
        (
            "MARKET",
            ("주가", "급락", "상승", "하락", "거래량"),
        ),
        (
            "COMPETITION",
            ("경쟁", "점유율", "추격", "공급 과잉"),
        ),
        (
            "POLICY",
            ("규제", "제재", "정책", "관세"),
        ),
    )
    EVENT_KEYWORDS = (
        (
            "PRICE_DROP",
            ("급락", "하락", "쇼크", "와르르", "투매", "약세"),
        ),
        (
            "PRICE_RISE",
            ("급등", "상승", "강세", "반등"),
        ),
        (
            "LISTING",
            ("상장", "기업공개", "IPO"),
        ),
    )
    NUMBER_PATTERN = re.compile(
        r"\d+(?:\.\d+)?"
        r"(?:%|퍼센트|원|억원|조원|달러|대|건|명)"
    )
    TITLE_PREFIX_PATTERN = re.compile(
        r"\[(?:속보|특징주|단독|종합|마켓뷰)[^\]]*\]"
    )
    TITLE_SUFFIX_PATTERN = re.compile(r"\(종합\d*\)")
    NON_WORD_PATTERN = re.compile(r"[^0-9A-Za-z가-힣]")
    SUMMARY_TOKEN_PATTERN = re.compile(
        r"[0-9A-Za-z가-힣]{2,}"
    )
    NUMBERED_SECTION_PATTERN = re.compile(
        r"(?m)^\s*\d+\.\s"
    )
    PERCENT_PATTERN = re.compile(
        r"[+-]?\d+(?:\.\d+)?%"
    )
    SUMMARY_STOP_WORDS = {
        "관련",
        "대한",
        "통해",
        "위해",
        "있는",
        "있다",
        "했다",
        "한다",
        "이번",
        "최근",
        "기자",
        "뉴스",
        "전망",
    }

    def __init__(
        self,
        max_articles: int = 3,
        summary_overlap_threshold: float = 0.6,
    ) -> None:
        if max_articles <= 0:
            raise ValueError(
                "max_articles must be greater than 0"
            )

        if not 0 < summary_overlap_threshold <= 1:
            raise ValueError(
                "summary_overlap_threshold must be "
                "greater than 0 and at most 1"
            )

        self.max_articles = max_articles
        self.summary_overlap_threshold = (
            summary_overlap_threshold
        )

    def select(
        self,
        articles: list[NewsArticle],
        target_name: str,
        target_code: str,
        as_of: datetime,
        require_direct_match: bool = True,
    ) -> list[NewsArticle]:
        ranked = sorted(
            (
                self._rank(
                    article,
                    target_name=target_name,
                    target_code=target_code,
                    as_of=as_of,
                )
                for article in articles
                if not self._is_advertisement(article)
                and not self._is_low_quality_listing(article)
                and (
                    not require_direct_match
                    or self._has_direct_reference(
                        article,
                        target_name=target_name,
                        target_code=target_code,
                    )
                    and not self._is_multi_topic_roundup(
                        article,
                        target_name=target_name,
                        target_code=target_code,
                    )
                )
            ),
            key=lambda item: (
                -item.score,
                -item.article.published_at.timestamp(),
                item.article.title,
                str(item.article.id),
            ),
        )
        deduplicated = self._deduplicate(ranked)
        selected: list[RankedNews] = []
        selected_article_keys = set()
        selected_topics = set()

        for item in deduplicated:
            if item.topic in selected_topics:
                continue

            selected.append(item)
            selected_article_keys.add(id(item.article))
            selected_topics.add(item.topic)

            if len(selected) == self.max_articles:
                break

        if len(selected) < self.max_articles:
            for item in deduplicated:
                if id(item.article) in selected_article_keys:
                    continue

                selected.append(item)
                selected_article_keys.add(id(item.article))

                if len(selected) == self.max_articles:
                    break

        return [item.article for item in selected]

    def _rank(
        self,
        article: NewsArticle,
        target_name: str,
        target_code: str,
        as_of: datetime,
    ) -> RankedNews:
        summary = article.summary or article.body
        text = f"{article.title} {summary}"
        score = 0

        if target_name and target_name in article.title:
            score += 30

        if target_code and target_code in article.title:
            score += 20

        if target_name and target_name in summary:
            score += 15

        if target_code and target_code in summary:
            score += 10

        score += min(
            30,
            sum(
                weight
                for keyword, weight
                in self.MATERIAL_KEYWORDS.items()
                if keyword in text
            ),
        )
        score += min(
            10,
            len(self.NUMBER_PATTERN.findall(text)) * 2,
        )
        score += self._recency_score(
            article.published_at,
            as_of,
        )

        if any(
            keyword in article.title
            for keyword in self.GENERIC_TITLE_KEYWORDS
        ):
            score -= 30

        return RankedNews(
            article=article,
            score=score,
            topic=self._classify_topic(text),
        )

    def _deduplicate(
        self,
        ranked: list[RankedNews],
    ) -> list[RankedNews]:
        result = []
        seen_news_codes = set()
        seen_titles = set()
        seen_event_keys = set()
        selected_summary_tokens: list[set[str]] = []

        for item in ranked:
            news_code = item.article.news_code
            normalized_title = self._normalize_title(
                item.article.title
            )
            summary_tokens = self._summary_tokens(
                item.article.summary or item.article.body
            )
            event_key = self._event_key(item.article.title)

            if (
                news_code
                and news_code in seen_news_codes
            ):
                continue

            if normalized_title in seen_titles:
                continue

            if any(
                self._summary_overlap(
                    summary_tokens,
                    existing_tokens,
                )
                >= self.summary_overlap_threshold
                for existing_tokens in selected_summary_tokens
            ):
                continue

            if event_key and event_key in seen_event_keys:
                continue

            result.append(item)
            seen_titles.add(normalized_title)
            selected_summary_tokens.append(summary_tokens)

            if news_code:
                seen_news_codes.add(news_code)

            if event_key:
                seen_event_keys.add(event_key)

        return result

    def _is_advertisement(
        self,
        article: NewsArticle,
    ) -> bool:
        text = (
            f"{article.title} "
            f"{article.summary or article.body}"
        )
        return any(
            keyword in text
            for keyword in self.ADVERTISEMENT_KEYWORDS
        )

    def _is_low_quality_listing(
        self,
        article: NewsArticle,
    ) -> bool:
        summary = article.summary or article.body

        if len(self.PERCENT_PATTERN.findall(article.title)) >= 3:
            return True

        return any(
            keyword in summary
            for keyword in self.LISTING_SUMMARY_KEYWORDS
        )

    @staticmethod
    def _has_direct_reference(
        article: NewsArticle,
        target_name: str,
        target_code: str,
    ) -> bool:
        summary = article.summary or article.body
        title_has_target = bool(
            target_name
            and target_name in article.title
            or target_code
            and target_code in article.title
        )

        if title_has_target:
            return True

        return bool(
            target_name
            and summary.count(target_name) >= 2
            or target_code
            and summary.count(target_code) >= 2
        )

    def _is_multi_topic_roundup(
        self,
        article: NewsArticle,
        target_name: str,
        target_code: str,
    ) -> bool:
        title_has_target = bool(
            target_name
            and target_name in article.title
            or target_code
            and target_code in article.title
        )

        if title_has_target:
            return False

        summary = article.summary or article.body
        return len(
            self.NUMBERED_SECTION_PATTERN.findall(summary)
        ) >= 3

    def _normalize_title(self, title: str) -> str:
        normalized = self.TITLE_PREFIX_PATTERN.sub("", title)
        normalized = self.TITLE_SUFFIX_PATTERN.sub(
            "",
            normalized,
        )
        return self.NON_WORD_PATTERN.sub(
            "",
            normalized,
        ).lower()

    def _summary_tokens(self, summary: str) -> set[str]:
        return {
            token.lower()
            for token in self.SUMMARY_TOKEN_PATTERN.findall(
                summary
            )
            if token not in self.SUMMARY_STOP_WORDS
        }

    @staticmethod
    def _summary_overlap(
        first: set[str],
        second: set[str],
    ) -> float:
        if not first or not second:
            return 0

        return len(first & second) / len(first | second)

    def _event_key(self, title: str) -> str | None:
        for event_key, keywords in self.EVENT_KEYWORDS:
            if any(keyword in title for keyword in keywords):
                return event_key

        return None

    def _classify_topic(self, text: str) -> str:
        for topic, keywords in self.TOPIC_KEYWORDS:
            if any(keyword in text for keyword in keywords):
                return topic

        return "OTHER"

    @staticmethod
    def _recency_score(
        published_at: datetime,
        as_of: datetime,
    ) -> int:
        if published_at.tzinfo is None:
            published_at = published_at.replace(
                tzinfo=timezone.utc
            )

        if as_of.tzinfo is None:
            as_of = as_of.replace(tzinfo=timezone.utc)

        age_hours = max(
            0,
            (as_of - published_at).total_seconds() / 3600,
        )

        if age_hours <= 6:
            return 20

        if age_hours <= 12:
            return 15

        if age_hours <= 24:
            return 10

        if age_hours <= 72:
            return 5

        return 0


class CommonSectionService:
    def __init__(
        self,
        news_repository: NewsRepository,
        target_repository: TargetRepository,
        section_repository: SectionRepository,
        ai_client: AiClient,
        news_selector: NewsSelector | None = None,
        max_concurrency: int = 5,
    ) -> None:
        if max_concurrency <= 0:
            raise ValueError(
                "max_concurrency must be greater than 0"
            )

        self.news_repository = news_repository
        self.target_repository = target_repository
        self.section_repository = section_repository
        self.ai_client = ai_client
        self.news_selector = news_selector or NewsSelector()
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
        stocks = self.target_repository.find_stocks(
            missing_stock_codes
        )
        industries = self.target_repository.find_industries(
            missing_industry_codes
        )

        targets: list[
            tuple[SectionType, str, str, list[NewsArticle]]
        ] = []
        self._collect_targets(
            section_type=SectionType.STOCK,
            codes=missing_stock_codes,
            news_by_code=news_by_stock,
            names_by_code={
                code: stock.corp_name
                for code, stock in stocks.items()
            },
            targets=targets,
            no_news_codes=result.no_news_stock_codes,
            as_of=period_end,
        )
        self._collect_targets(
            section_type=SectionType.INDUSTRY,
            codes=missing_industry_codes,
            news_by_code=news_by_industry,
            names_by_code={
                code: industry.industry_name
                for code, industry in industries.items()
            },
            targets=targets,
            no_news_codes=result.no_news_industry_codes,
            as_of=period_end,
        )

        responses = await asyncio.gather(
            *[
                self._generate_response(
                    section_type=section_type,
                    target_code=target_code,
                    target_name=target_name,
                    news_articles=news_articles,
                )
                for (
                    section_type,
                    target_code,
                    target_name,
                    news_articles,
                ) in targets
            ],
            return_exceptions=True,
        )

        for target, response in zip(targets, responses):
            section_type, target_code, _, _ = target

            if isinstance(
                response,
                (AiResponseInvalidError, OpenAIError, TimeoutError),
            ):
                self._failed_codes(result, section_type).add(
                    target_code
                )
                continue

            if isinstance(response, BaseException):
                raise response

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
        target_name: str,
        news_articles: list[NewsArticle],
    ) -> CommonSectionAiResponse:
        source = self._build_source(
            section_type=section_type,
            target_code=target_code,
            target_name=target_name,
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
        return (
            self.section_repository
            .save_common_section_with_lines_or_get(
                section,
                lines,
            )
        )

    def _collect_targets(
        self,
        section_type: SectionType,
        codes: list[str],
        news_by_code: dict[str, list[NewsArticle]],
        names_by_code: dict[str, str],
        targets: list[
            tuple[SectionType, str, str, list[NewsArticle]]
        ],
        no_news_codes: set[str],
        as_of: datetime,
    ) -> None:
        for code in codes:
            target_name = names_by_code.get(code, code)
            raw_news_articles = news_by_code.get(code, [])
            logger.info(
                "common_section_news_before_selection "
                "target_type=%s target_code=%s target_name=%s "
                "news_count=%d",
                section_type.value,
                code,
                target_name,
                len(raw_news_articles),
            )
            news_articles = self.news_selector.select(
                raw_news_articles,
                target_name=target_name,
                target_code=code,
                as_of=as_of,
                require_direct_match=(
                    section_type == SectionType.STOCK
                ),
            )
            logger.info(
                "common_section_news_after_selection "
                "target_type=%s target_code=%s target_name=%s "
                "news_count=%d",
                section_type.value,
                code,
                target_name,
                len(news_articles),
            )

            if news_articles:
                targets.append(
                    (
                        section_type,
                        code,
                        target_name,
                        news_articles,
                    )
                )
            else:
                no_news_codes.add(code)

    @staticmethod
    def _build_source(
        section_type: SectionType,
        target_code: str,
        target_name: str,
        news_articles: list[NewsArticle],
    ) -> str:
        target_label = (
            "종목 코드"
            if section_type == SectionType.STOCK
            else "업종 코드"
        )
        parts = [
            f"{target_label}: {target_code}",
            f"대상 이름: {target_name}",
            "지정 기간의 뉴스 요약:",
        ]

        for index, article in enumerate(news_articles, start=1):
            parts.append(
                "\n".join(
                    [
                        f"뉴스 {index}",
                        f"제목: {article.title}",
                        f"요약: {article.summary or article.body}",
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
