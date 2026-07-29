from dataclasses import dataclass, field
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from script_app.models import (
    NewsArticle,
    NewsIndustryMapping,
    NewsStockMapping,
    Section,
    SectionLine,
    SectionType,
    Script,
    ScriptStatus,
    ScriptSection,
    Stock,
    Industry,
    IndustryPrice,
    MarketPrice,
    UserIndustry,
    UserStock,
)


@dataclass
class UserInterestTargets:
    stock_codes: list[str] = field(default_factory=list)
    industry_codes: list[str] = field(default_factory=list)


class UserInterestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_by_user_ids(
        self,
        user_ids: list[UUID],
    ) -> dict[UUID, UserInterestTargets]:
        unique_user_ids = list(dict.fromkeys(user_ids))
        targets_by_user = {
            user_id: UserInterestTargets()
            for user_id in unique_user_ids
        }

        if not unique_user_ids:
            return targets_by_user

        stock_stmt = (
            select(
                UserStock.user_id,
                UserStock.stock_code,
            )
            .where(UserStock.user_id.in_(unique_user_ids))
            .order_by(
                UserStock.user_id,
                UserStock.stock_code,
            )
        )

        for user_id, stock_code in self.session.execute(stock_stmt):
            targets_by_user[user_id].stock_codes.append(stock_code)

        industry_stmt = (
            select(
                UserIndustry.user_id,
                UserIndustry.industry_code,
            )
            .where(UserIndustry.user_id.in_(unique_user_ids))
            .order_by(
                UserIndustry.user_id,
                UserIndustry.industry_code,
            )
        )

        for user_id, industry_code in self.session.execute(
            industry_stmt
        ):
            targets_by_user[user_id].industry_codes.append(
                industry_code
            )

        return targets_by_user


class TargetRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_stocks(
        self,
        stock_codes: list[str],
    ) -> dict[str, Stock]:
        unique_stock_codes = list(dict.fromkeys(stock_codes))

        if not unique_stock_codes:
            return {}

        stmt = select(Stock).where(
            Stock.stock_code.in_(unique_stock_codes)
        )
        return {
            stock.stock_code: stock
            for stock in self.session.scalars(stmt)
        }

    def find_industries(
        self,
        industry_codes: list[str],
    ) -> dict[str, Industry]:
        unique_industry_codes = list(
            dict.fromkeys(industry_codes)
        )

        if not unique_industry_codes:
            return {}

        stmt = select(Industry).where(
            Industry.industry_code.in_(unique_industry_codes)
        )
        return {
            industry.industry_code: industry
            for industry in self.session.scalars(stmt)
        }


@dataclass(frozen=True)
class SectionLineData:
    talker: str
    content: str


class SectionRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_stock_sections(
        self,
        stock_codes: list[str],
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Section]:
        unique_stock_codes = list(dict.fromkeys(stock_codes))

        if not unique_stock_codes:
            return {}

        stmt = select(Section).where(
            Section.section_type == SectionType.STOCK,
            Section.stock_code.in_(unique_stock_codes),
            Section.period_start == period_start,
            Section.period_end == period_end,
        )

        sections = self.session.scalars(stmt)
        return {
            section.stock_code: section
            for section in sections
            if section.stock_code is not None
        }

    def find_industry_sections(
        self,
        industry_codes: list[str],
        period_start: datetime,
        period_end: datetime,
    ) -> dict[str, Section]:
        unique_industry_codes = list(
            dict.fromkeys(industry_codes)
        )

        if not unique_industry_codes:
            return {}

        stmt = select(Section).where(
            Section.section_type == SectionType.INDUSTRY,
            Section.industry_code.in_(unique_industry_codes),
            Section.period_start == period_start,
            Section.period_end == period_end,
        )

        sections = self.session.scalars(stmt)
        return {
            section.industry_code: section
            for section in sections
            if section.industry_code is not None
        }

    def save_with_lines(
        self,
        section: Section,
        lines: list[SectionLineData],
    ) -> Section:
        self.session.add(section)
        self.session.flush()

        self.session.add_all(
            [
                SectionLine(
                    section_id=section.id,
                    line_order=line_order,
                    talker=line.talker,
                    content=line.content,
                )
                for line_order, line in enumerate(lines, start=1)
            ]
        )
        self.session.flush()

        return section

    def save_common_section_with_lines_or_get(
        self,
        section: Section,
        lines: list[SectionLineData],
    ) -> Section:
        if section.section_type not in (
            SectionType.STOCK,
            SectionType.INDUSTRY,
        ):
            raise ValueError(
                "only common sections support conflict reuse"
            )

        try:
            with self.session.begin_nested():
                return self.save_with_lines(section, lines)
        except IntegrityError:
            existing_section = self._find_matching_common_section(
                section
            )

            if existing_section is None:
                raise

            return existing_section

    def find_lines_by_section_ids(
        self,
        section_ids: list[UUID],
    ) -> dict[UUID, list[SectionLine]]:
        unique_section_ids = list(dict.fromkeys(section_ids))
        lines_by_section = {
            section_id: []
            for section_id in unique_section_ids
        }

        if not unique_section_ids:
            return lines_by_section

        stmt = (
            select(SectionLine)
            .where(SectionLine.section_id.in_(unique_section_ids))
            .order_by(
                SectionLine.section_id,
                SectionLine.line_order,
            )
        )

        for line in self.session.scalars(stmt):
            lines_by_section[line.section_id].append(line)

        return lines_by_section

    def delete_by_id(self, section_id: UUID) -> bool:
        section = self.session.get(Section, section_id)

        if section is None:
            return False

        is_referenced = self.session.scalar(
            select(func.count())
            .select_from(ScriptSection)
            .where(ScriptSection.section_id == section_id)
        )

        if is_referenced:
            raise SectionInUseError(section_id)

        self.session.execute(
            delete(SectionLine).where(
                SectionLine.section_id == section_id
            )
        )
        self.session.delete(section)
        self.session.flush()
        return True

    def _find_matching_common_section(
        self,
        section: Section,
    ) -> Section | None:
        stmt = select(Section).where(
            Section.section_type == section.section_type,
            Section.period_start == section.period_start,
            Section.period_end == section.period_end,
        )

        if section.section_type == SectionType.STOCK:
            stmt = stmt.where(
                Section.stock_code == section.stock_code
            )
        else:
            stmt = stmt.where(
                Section.industry_code == section.industry_code
            )

        return self.session.scalar(stmt)


class ScriptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_completed_scripts(
        self,
        user_ids: list[UUID],
        period_start: datetime,
        period_end: datetime,
    ) -> dict[UUID, Script]:
        unique_user_ids = list(dict.fromkeys(user_ids))

        if not unique_user_ids:
            return {}

        stmt = select(Script).where(
            Script.user_id.in_(unique_user_ids),
            Script.period_start == period_start,
            Script.period_end == period_end,
            Script.status == ScriptStatus.COMPLETED,
        )

        return {
            script.user_id: script
            for script in self.session.scalars(stmt)
        }

    def find_scripts(
        self,
        user_ids: list[UUID],
        period_start: datetime,
        period_end: datetime,
    ) -> dict[UUID, Script]:
        unique_user_ids = list(dict.fromkeys(user_ids))

        if not unique_user_ids:
            return {}

        stmt = select(Script).where(
            Script.user_id.in_(unique_user_ids),
            Script.period_start == period_start,
            Script.period_end == period_end,
        )
        return {
            script.user_id: script
            for script in self.session.scalars(stmt)
        }

    def find_script(
        self,
        user_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> Script | None:
        stmt = select(Script).where(
            Script.user_id == user_id,
            Script.period_start == period_start,
            Script.period_end == period_end,
        )
        return self.session.scalar(stmt)

    def create_generating_script(
        self,
        user_id: UUID,
        period_start: datetime,
        period_end: datetime,
    ) -> Script:
        script = Script(
            user_id=user_id,
            period_start=period_start,
            period_end=period_end,
            status=ScriptStatus.GENERATING,
        )
        self.session.add(script)
        self.session.flush()
        return script

    def add_sections(
        self,
        script: Script,
        sections: list[Section],
    ) -> list[ScriptSection]:
        script_sections = [
            ScriptSection(
                script_id=script.id,
                section_id=section.id,
                section_order=section_order,
                section_type=section.section_type,
            )
            for section_order, section in enumerate(
                sections,
                start=1,
            )
        ]
        self.session.add_all(script_sections)
        self.session.flush()
        return script_sections

    def update_status(
        self,
        script: Script,
        status: ScriptStatus,
    ) -> Script:
        script.status = status
        self.session.flush()
        return script

    def retry_failed_script(
        self,
        script: Script,
    ) -> Script:
        if script.status != ScriptStatus.FAILED:
            raise ValueError(
                "only failed scripts can be retried"
            )

        script_sections = self.find_sections(script.id)
        personal_section_ids = [
            item.section_id
            for item in script_sections
            if item.section_type
            in (
                SectionType.OPENING,
                SectionType.BRIDGE,
                SectionType.CLOSING,
            )
        ]

        for script_section in script_sections:
            self.session.delete(script_section)

        self.session.flush()

        if personal_section_ids:
            personal_sections = self.session.scalars(
                select(Section).where(
                    Section.id.in_(personal_section_ids)
                )
            )

            for section in personal_sections:
                self.session.delete(section)

        script.status = ScriptStatus.GENERATING
        self.session.flush()
        return script

    def find_sections(
        self,
        script_id: UUID,
    ) -> list[ScriptSection]:
        stmt = (
            select(ScriptSection)
            .where(ScriptSection.script_id == script_id)
            .order_by(ScriptSection.section_order)
        )
        return list(self.session.scalars(stmt))

    def get_script_text(self, script_id: UUID) -> str:
        stmt = (
            select(
                SectionLine.talker,
                SectionLine.content,
            )
            .join(
                ScriptSection,
                ScriptSection.section_id
                == SectionLine.section_id,
            )
            .where(ScriptSection.script_id == script_id)
            .order_by(
                ScriptSection.section_order,
                SectionLine.line_order,
            )
        )
        return "\n".join(
            f"{talker}: {content}"
            for talker, content in self.session.execute(stmt)
        )

    def delete_by_id(self, script_id: UUID) -> bool:
        script = self.session.get(Script, script_id)

        if script is None:
            return False

        script_sections = self.find_sections(script_id)
        personal_section_ids = [
            item.section_id
            for item in script_sections
            if item.section_type
            in (
                SectionType.OPENING,
                SectionType.BRIDGE,
                SectionType.CLOSING,
            )
        ]

        for script_section in script_sections:
            self.session.delete(script_section)

        self.session.flush()
        self.session.delete(script)

        for section_id in personal_section_ids:
            is_referenced = self.session.scalar(
                select(func.count())
                .select_from(ScriptSection)
                .where(ScriptSection.section_id == section_id)
            )

            if is_referenced:
                continue

            self.session.execute(
                delete(SectionLine).where(
                    SectionLine.section_id == section_id
                )
            )
            section = self.session.get(Section, section_id)

            if section is not None:
                self.session.delete(section)

        self.session.flush()
        return True


class SectionInUseError(Exception):
    def __init__(self, section_id: UUID) -> None:
        super().__init__(
            f"section {section_id} is referenced by a script"
        )


class NewsRepository:

    def __init__(self, session: Session):
        self.session = session

    def find_by_stock_codes(
        self,
        stock_codes: list[str],
        start_at: datetime,
        end_at: datetime,
    ) -> dict[str, list[NewsArticle]]:
        unique_stock_codes = list(dict.fromkeys(stock_codes))
        news_by_stock = {
            stock_code: []
            for stock_code in unique_stock_codes
        }

        if not unique_stock_codes:
            return news_by_stock

        stmt = (
            select(
                NewsStockMapping.stock_code,
                NewsArticle,
            )
            .join(
                NewsArticle,
                NewsArticle.id == NewsStockMapping.news_id,
            )
            .where(
                NewsStockMapping.stock_code.in_(
                    unique_stock_codes
                ),
                NewsArticle.published_at >= start_at,
                NewsArticle.published_at < end_at,
            )
            .order_by(
                NewsStockMapping.stock_code,
                NewsArticle.published_at,
                NewsArticle.id,
            )
        )

        for stock_code, news_article in self.session.execute(stmt):
            news_by_stock[stock_code].append(news_article)

        return news_by_stock

    def find_by_industry_codes(
        self,
        industry_codes: list[str],
        start_at: datetime,
        end_at: datetime,
    ) -> dict[str, list[NewsArticle]]:
        unique_industry_codes = list(
            dict.fromkeys(industry_codes)
        )
        news_by_industry = {
            industry_code: []
            for industry_code in unique_industry_codes
        }

        if not unique_industry_codes:
            return news_by_industry

        stmt = (
            select(
                NewsIndustryMapping.industry_code,
                NewsArticle,
            )
            .join(
                NewsArticle,
                NewsArticle.id == NewsIndustryMapping.news_id,
            )
            .where(
                NewsIndustryMapping.industry_code.in_(
                    unique_industry_codes
                ),
                NewsArticle.published_at >= start_at,
                NewsArticle.published_at < end_at,
            )
            .order_by(
                NewsIndustryMapping.industry_code,
                NewsArticle.published_at,
                NewsArticle.id,
            )
        )

        for industry_code, news_article in self.session.execute(
            stmt
        ):
            news_by_industry[industry_code].append(news_article)

        return news_by_industry


class PriceRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_latest_stock_prices(
        self,
        stock_codes: list[str],
        as_of: datetime,
        provider: str = "KOSCOM",
    ) -> dict[str, MarketPrice]:
        unique_stock_codes = list(dict.fromkeys(stock_codes))

        if not unique_stock_codes:
            return {}

        row_number = func.row_number().over(
            partition_by=MarketPrice.stock_code,
            order_by=(
                MarketPrice.traded_at.desc(),
                MarketPrice.id.desc(),
            ),
        )
        ranked_prices = (
            select(
                MarketPrice.id.label("price_id"),
                row_number.label("row_number"),
            )
            .where(
                MarketPrice.stock_code.in_(unique_stock_codes),
                MarketPrice.traded_at < as_of,
                MarketPrice.interval == "DAILY",
                MarketPrice.provider == provider,
            )
            .subquery()
        )
        stmt = (
            select(MarketPrice)
            .join(
                ranked_prices,
                ranked_prices.c.price_id == MarketPrice.id,
            )
            .where(ranked_prices.c.row_number == 1)
            .order_by(MarketPrice.stock_code)
        )

        return {
            price.stock_code: price
            for price in self.session.scalars(stmt)
        }

    def find_latest_industry_prices(
        self,
        industry_codes: list[str],
        as_of: datetime,
        provider: str = "KOSCOM",
    ) -> dict[str, IndustryPrice]:
        unique_industry_codes = list(
            dict.fromkeys(industry_codes)
        )

        if not unique_industry_codes:
            return {}

        row_number = func.row_number().over(
            partition_by=IndustryPrice.industry_code,
            order_by=(
                IndustryPrice.traded_at.desc(),
                IndustryPrice.id.desc(),
            ),
        )
        ranked_prices = (
            select(
                IndustryPrice.id.label("price_id"),
                row_number.label("row_number"),
            )
            .where(
                IndustryPrice.industry_code.in_(
                    unique_industry_codes
                ),
                IndustryPrice.traded_at < as_of,
                IndustryPrice.provider == provider,
            )
            .subquery()
        )
        stmt = (
            select(IndustryPrice)
            .join(
                ranked_prices,
                ranked_prices.c.price_id == IndustryPrice.id,
            )
            .where(ranked_prices.c.row_number == 1)
            .order_by(IndustryPrice.industry_code)
        )

        return {
            price.industry_code: price
            for price in self.session.scalars(stmt)
        }
